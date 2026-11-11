import pandas as pd, numpy as np, glob, re, os, random, json
from functools import lru_cache
ROOT='/mnt/c/Users/krist/Documents/Danae/tennis/tml-data'
OUT=os.path.dirname(os.path.abspath(__file__))
TOK=re.compile(r'^(\d+)-(\d+)(?:\(\d+\))?$')

def parse(score):
    """list of (gw,gl,is_tb) from winner's perspective; None if non-standard/incomplete"""
    if not isinstance(score,str): return None
    out=[]
    for t in score.split():
        m=TOK.match(t)
        if not m: return None
        a,b=int(m[1]),int(m[2])
        tb=(a,b) in((7,6),(6,7))
        ok=tb or (max(a,b)==6 and min(a,b)<=4) or (max(a,b)>=7 and abs(a-b)==2 and max(a,b)>=7)
        if not ok: return None
        out.append((a,b,tb))
    return out or None

def ngames(s):  # games for serve alternation (tiebreak = 1 game)
    a,b,tb=s; return 13 if tb else a+b

def load():
    fs=[f for f in sorted(glob.glob(ROOT+'/*.csv')) if re.search(r'/(19[89]\d|20\d\d)\.csv$',f)]
    d=pd.concat([pd.read_csv(f,low_memory=False) for f in fs],ignore_index=True)
    d['year']=d.tourney_date//10000
    return d

def build(d):
    rows=[]; val=dict(n=0,n_tb=0,fits_some=0,fits_some_tb=0,fits_one=0,fits_both=0)
    for r in d.itertuples():
        sets=parse(r.score)
        if sets is None or pd.isna(r.w_SvGms) or pd.isna(r.l_SvGms): continue
        # completeness: winner must win required sets
        bo=int(r.best_of); need=bo//2+1
        ws=sum(a>b for a,b,_ in sets)
        if ws!=need or sum(a<b for a,b,_ in sets)>=need: continue
        if any(a>b for a,b,_ in sets[:0]): pass
        def served(first_w):
            # games served by (winner, loser) under hypothesis; tiebreak point-games not counted in SvGms
            pre=0; sw=sl=0
            for a_,b_,tb_ in sets:
                n=12 if tb_ else a_+b_
                x_is_first = (pre%2==0)           # server of game 1 of this set is match-first-server?
                x_w = (x_is_first==first_w)       # ... is that the winner?
                hi,lo=(n+1)//2,n//2
                if x_w: sw+=hi; sl+=lo
                else: sl+=hi; sw+=lo
                pre+=ngames((a_,b_,tb_))
            return sw,sl
        obs=(int(r.w_SvGms),int(r.l_SvGms))
        hw=served(True)==obs; hl=served(False)==obs
        val['n']+=1; ntb=any(s_[2] for s_ in sets); val['n_tb']+=ntb
        val['fits_some']+= (hw or hl); val['fits_some_tb']+= ((hw or hl) and ntb)
        val['fits_one']+= (hw!=hl); val['fits_both']+= (hw and hl)
        if not (hw or hl): continue
        first='w' if (hw and not hl) else 'l' if (hl and not hw) else None
        N=sum(ngames(s_) for s_ in sets)
        rows.append((r.year,r.surface,r.tourney_level,bo,sets,N,first,r.winner_rank,r.loser_rank,r.winner_id,r.loser_id,hw and hl,(r.w_1stWon+r.w_2ndWon)/r.w_svpt if r.w_svpt>0 else np.nan,(r.l_1stWon+r.l_2ndWon)/r.l_svpt if r.l_svpt>0 else np.nan))
    return rows,val

def setrecords(rows):
    recs=[]
    for year,surf,lvl,bo,sets,N,first,wr,lr,wid,lid,_amb,_a,_b in rows:
        if first is None: continue
        pre=0
        for k,(a,b,tb) in enumerate(sets,1):
            fs_is_w = (first=='w') == (pre%2==0)   # first server of this set is match winner?
            fs_won = (a>b) if fs_is_w else (a<b)
            fr,orank=(wr,lr) if fs_is_w else (lr,wr)
            recs.append((year,surf,lvl,bo,k,int(fs_won),tb,fr,orank,k==len(sets)))
            pre+=ngames((a,b,tb))
    return pd.DataFrame(recs,columns='year surface level bo setno won tb r_fs r_opp last'.split())

def ci(p,n): 
    se=np.sqrt(p*(1-p)/n); return p-1.96*se,p+1.96*se
def summ(g): 
    n=len(g); p=g.won.mean(); lo,hi=ci(p,n); return pd.Series(dict(n=n,p=p,lo=lo,hi=hi))

def logit_fit(X,y,it=30):
    b=np.zeros(X.shape[1])
    for _ in range(it):
        p=1/(1+np.exp(-X@b)); W=p*(1-p)
        H=X.T@(X*W[:,None]); b=b+np.linalg.solve(H,X.T@(y-p))
    cov=np.linalg.inv(H); return b,np.sqrt(np.diag(cov))

# ---------- Markov ----------
def game_hold(p):
    q=1-p
    return p**4*(1+4*q+10*q*q)+20*p**3*q**3*p*p/(1-2*p*q)
@lru_cache(None)
def tb_win(pa,pb):
    """P(A wins tiebreak), A serves first; pa/pb = point-win prob on own serve. DP over points."""
    @lru_cache(None)
    def f(x,y):
        if x>=7 and x-y>=2: return 1.0
        if y>=7 and y-x>=2: return 0.0
        if x>=6 and y>=6:  # deuce-like: closed form over pairs
            # at (n,n) or +-1; use 2-point cycles: A serves 1 point & B serves 1 point alternates
            pass
        t=x+y; a_serves=((t+1)//2)%2==0
        pw=pa if a_serves else 1-pb
        return pw*f(x+1,y)+(1-pw)*f(x,y+1) if not(x>=6 and y>=6) else g(x-y,a_serves)
    @lru_cache(None)
    def g(dif,a_serves): # iterate numerically for extended tb
        v={d:0.5 for d in (-1,0,1)}
        # approximate by many rounds: simulate 2-point cycles starting from tie with A serving 1st of pair is not exact; use value iteration on (diff,server parity)
        V={(d,s):0.5 for d in range(-1,2) for s in (0,1)}
        for _ in range(200):
            N={}
            for d in range(-1,2):
                for s in (0,1):
                    pw=pa if s==0 else 1-pb
                    up=1.0 if d+1==2 else V[(d+1,1-s)] if True else 0
                    dn=0.0 if d-1==-2 else V[(d-1,1-s)]
                    N[(d,s)]=pw*up+(1-pw)*dn
            V=N
        return V[(dif,0 if a_serves else 1)]
    return f(0,0)

def set_win_first_server(pa,pb):
    """P(A wins set), A serves game 1. pa,pb point-win prob on own serve."""
    ha,hb=game_hold(pa),game_hold(pb)
    T=tb_win(round(pa,6),round(pb,6))
    @lru_cache(None)
    def f(x,y):  # x=A games, y=B games; A serves when x+y even
        if x==7 and y<=5 or x==7 and y==6 and False: return 1.0
        if y==7 and x<=5: return 0.0
        if x==6 and y<=4: return 1.0
        if y==6 and x<=4: return 0.0
        if x==6 and y==6: return T
        if x==7 and y==6: return 1.0
        if y==7 and x==6: return 0.0
        h=ha if (x+y)%2==0 else 1-hb   # prob A wins game
        return h*f(x+1,y)+(1-h)*f(x,y+1)
    return f(0,0)

def simulate(n=200000,m=0.645,sd_d=0.025,seed=1):
    """Monte Carlo bo3 matches; returns P(FS wins set1) overall and conditioned on odd total games,
       and P(FS wins set k) for k=2,3 overall vs odd-N."""
    rng=np.random.default_rng(seed); R=random.Random(seed)
    res=[]
    for _ in range(n):
        d=rng.normal(0,sd_d); pa=m+d; pb=m-d     # A: first server of match (coin toss => independent of d)
        if R.random()<.5: pa,pb=pb,pa
        ha,hb=game_hold(pa),game_hold(pb)
        pre=0; sw=[]; fsw=[]; ws=[0,0]
        first_is_A=True
        while max(ws)<2:
            x=y=0; a_serves_first=(pre%2==0)
            g=0
            while True:
                aserv=((g%2==0)==a_serves_first)
                if aserv: awin=R.random()<ha
                else: awin=R.random()>hb
                x+=awin; y+=not awin; g+=1
                if x==6 and y==6:
                    # tiebreak
                    s=0;t=0;i=0
                    while True:
                        srv_a=(((i+1)//2)%2==0)==a_serves_first
                        pw=pa if srv_a else 1-pb
                        if R.random()<pw: s+=1
                        else: t+=1
                        i+=1
                        if max(s,t)>=7 and abs(s-t)>=2: break
                    awin=s>t; g+=1; x+=awin; y+=not awin; break
                if (max(x,y)>=6 and abs(x-y)>=2): break
            awin=x>y; ws[0 if awin else 1]+=1
            fsw.append(awin if a_serves_first else not awin)
            pre+=g
        res.append((pre,fsw))
    odd=[r for r in res if r[0]%2==1]
    out={}
    for k in range(3):
        a=[r[1][k] for r in res if len(r[1])>k]; b=[r[1][k] for r in odd if len(r[1])>k]
        out[f'set{k+1}_all']=(float(np.mean(a)),len(a)); out[f'set{k+1}_oddN']=(float(np.mean(b)),len(b))
    return out


# ================= EM (MAR) estimator =================
from collections import defaultdict
def prep_em(rows, nbins=5):
    """Convert to A/B (A = better ranked) representation. Returns list of groups."""
    g=[]; lr_all=[]
    for (year,surf,lvl,bo,sets,N,first,wr,lr,wid,lid,amb,*_x) in rows:
        if pd.isna(wr) or pd.isna(lr) or wr==lr: continue
        lr_all.append(np.log(max(wr,lr)/min(wr,lr)))
    edges=np.quantile(lr_all,np.linspace(0,1,nbins+1)[1:-1])
    for (year,surf,lvl,bo,sets,N,first,wr,lr,wid,lid,amb,*_x) in rows:
        if pd.isna(wr) or pd.isna(lr) or wr==lr: continue
        Aw = wr<lr
        bin_=int(np.searchsorted(edges,np.log(max(wr,lr)/min(wr,lr))))
        seqA=tuple((a,b,tb) if Aw else (b,a,tb) for a,b,tb in sets)
        F=None if first is None else ('A' if (first=='w')==Aw else 'B')
        g.append((bo,bin_,surf,seqA,F))
    return g

def em_fit(groups,iters=40,sets_idx_cap=3):
    cnt=defaultdict(float)
    for bo,b,surf,seq,F in groups: cnt[(bo,b,seq,F)]+=1
    items=list(cnt.items())
    cats={}
    def cat(o): 
        if o not in cats: cats[o]=len(cats)
        return cats[o]
    # precompute per item: for each hypothesis, list of (pikey, cat)
    pre=[]
    for (bo,b,seq,F),n in items:
        hyp={}
        for h in ('A','B'):
            lst=[]; p=0
            for j,(ga,gb,tb) in enumerate(seq):
                firstA=((p%2==0)==(h=='A'))
                lst.append(((bo,b,min(j,sets_idx_cap-1),0 if firstA else 1),cat((ga,gb,tb)),firstA,ga>gb))
                p+=ngames((ga,gb,tb))
            hyp[h]=lst
        pre.append(hyp)
    K=len(cats); pis=defaultdict(lambda: np.full(K,1e-3))
    post=[]
    for (key,n),hyp in zip(items,pre):
        F=key[3]; post.append({'A':1.0,'B':0.0} if F=='A' else {'A':0.0,'B':1.0} if F=='B' else {'A':.5,'B':.5})
    for it in range(iters+1):
        # M step
        cn=defaultdict(lambda: np.full(K,0.5))
        for ((key,n),hyp,w) in zip(items,pre,post):
            for h in 'AB':
                if w[h]==0: continue
                for pk,c,_,_ in hyp[h]: cn[pk][c]+=n*w[h]
        pis={k:v/v.sum() for k,v in cn.items()}
        if it==iters: break
        # E step (only ambiguous)
        for idx,((key,n),hyp) in enumerate(zip(items,pre)):
            if key[3] is not None: continue
            ll={h:sum(np.log(pis[pk][c]) for pk,c,_,_ in hyp[h]) for h in 'AB'}
            m=max(ll.values()); e={h:np.exp(ll[h]-m) for h in 'AB'}; z=e['A']+e['B']
            post[idx]={h:e[h]/z for h in 'AB'}
    return items,pre,post

def em_estimates(groups,iters=40,by=None):
    """returns dict of weighted estimates; also keyed by set number / surface"""
    items,pre,post=em_fit(groups,iters)
    acc=defaultdict(lambda:[0.0,0.0])
    for ((key,n),hyp,w) in zip(items,pre,post):
        bo,b,seq,F=key
        # surface lookup not stored in key: handled by separate fit call
        for j in range(len(seq)):
            pw=0.0
            for h in 'AB':
                _,_,firstA,Awon=hyp[h][j]
                pw+=w[h]*(1.0 if firstA==Awon else 0.0)
            for lab in ('all','first_set' if j==0 else 'later',f'set{min(j+1,5)}'):
                acc[lab][0]+=n*pw; acc[lab][1]+=n
    return {k:(v[0]/v[1],v[1]) for k,v in acc.items()}

def em_boot(groups,B=30,seed=0):
    rng=np.random.default_rng(seed); out=[]
    n=len(groups)
    for _ in range(B):
        idx=rng.integers(0,n,n); gs=[groups[i] for i in idx]
        out.append(em_estimates(gs,25))
    keys=out[0].keys()
    return {k:(float(np.percentile([o[k][0] for o in out if k in o],2.5)),float(np.percentile([o[k][0] for o in out if k in o],97.5))) for k in keys}

# ================= simulation-based validation of the EM estimator =================
def sim_matches(n=100000,m=0.627,sd_d=0.03,seed=3,bo=3):
    """Simulate bo3 matches; A = the player with larger d (stronger). Returns groups like prep_em (with F hidden when ambiguous)
       and the TRUE first-server set win rates."""
    rng=np.random.default_rng(seed); R=random.Random(seed)
    groups=[]; truth=defaultdict(lambda:[0,0]); ds=[]
    for _ in range(n):
        d=rng.normal(0,sd_d); Aser=m+d; Bser=m-d   # strength shifts both serve and return
        ds.append(abs(d))
        A_first = R.random()<.5
        ha,hb=game_hold(Aser),game_hold(Bser)
        pre=0; seq=[]; wins=[0,0]; fsl=[]
        while max(wins)<2:
            a_first_set=((pre%2==0)==A_first)
            x=y=g=0
            while True:
                aserv=((g%2==0)==a_first_set)
                awin = (R.random()<ha) if aserv else (R.random()>hb)
                x+=awin; y+=(not awin); g+=1
                if x==6 and y==6:
                    s_=t_=i=0
                    while True:
                        srv_a=(((i+1)//2)%2==0)==a_first_set
                        if R.random()<(Aser if srv_a else 1-Bser): s_+=1
                        else: t_+=1
                        i+=1
                        if max(s_,t_)>=7 and abs(s_-t_)>=2: break
                    aw=s_>t_; x+=aw; y+=(not aw); g+=1; break
                if max(x,y)>=6 and abs(x-y)>=2: break
            tb=(x,y) in((7,6),(6,7))
            seq.append((x,y,tb)); wins[0 if x>y else 1]+=1
            fsl.append(((x>y) if a_first_set else (y>x)))
            pre+=ngames((x,y,tb))
        for j,v in enumerate(fsl):
            for lab in ('all','first_set' if j==0 else 'later',f'set{min(j+1,5)}'):
                truth[lab][0]+=v; truth[lab][1]+=1
        # identification exactly as in real data
        def served(first_is_A):
            p=0; sa=sb=0
            for a_,b_,tb_ in seq:
                nn=12 if tb_ else a_+b_
                xa=((p%2==0)==first_is_A); hi,lo=(nn+1)//2,nn//2
                if xa: sa+=hi; sb+=lo
                else: sb+=hi; sa+=lo
                p+=ngames((a_,b_,tb_))
            return sa,sb
        obs=served(A_first); hA=served(True)==obs; hB=served(False)==obs
        F='A' if (hA and not hB) else 'B' if (hB and not hA) else None
        groups.append((3,0,'x',tuple(seq),F))
    # bins by |d| are unavailable in practice; use rank-like proxy: strength bin from quantiles of |d| with noise
    ds=np.array(ds); edges=np.quantile(ds,[.2,.4,.6,.8])
    groups=[(bo_,int(np.searchsorted(edges,di)),sf,sq,F) for (bo_,_,sf,sq,F),di in zip(groups,ds)]
    return groups,{k:v[0]/v[1] for k,v in truth.items()}

if __name__=='__main__':
    d=load(); rows,val=build(d); res={'validation_serve_order_inference':val}
    res['avg_serve_point_win']=float(((lambda ss:((ss.w_1stWon+ss.w_2ndWon).sum()+(ss.l_1stWon+ss.l_2ndWon).sum())/(ss.w_svpt.sum()+ss.l_svpt.sum()))(d.dropna(subset=['w_svpt']))))
    # (1) NAIVE: only matches where the first server is uniquely identified
    S=setrecords(rows)
    res['naive_identified_only']={'overall':summ(S).to_dict(),
        'set1':summ(S[S.setno==1]).to_dict(),'later':summ(S[S.setno>1]).to_dict(),
        'by_set':{int(k):v for k,v in S.groupby(S.setno.clip(upper=5)).apply(summ).round(4).to_dict('index').items()},
        'p_matchfirstserver_wins_match':float(np.mean([r[6]=='w' for r in rows if r[6]])),
        'n_matches_identified':int(sum(r[6] is not None for r in rows)),'n_matches_total':len(rows)}
    # (2) EM / MAR estimator using all matches
    G=prep_em(rows); res['n_matches_em']=len(G)
    est=em_estimates(G,40); ci_=em_boot(G,30)
    res['em_overall']={k:dict(p=float(v[0]),n_sets=int(v[1]),ci=ci_[k]) for k,v in est.items()}
    sf={}
    for surf in ['Hard','Clay','Grass','Carpet']:
        gs=[x for x in G if x[2]==surf]; e=em_estimates(gs,40)
        sf[surf]={k:dict(p=float(e[k][0]),n_sets=int(e[k][1])) for k in ['first_set','later','all'] if k in e}; sf[surf]['n_matches']=len(gs)
    res['em_by_surface']=sf
    bo={}
    for b in (3,5):
        gs=[x for x in G if x[0]==b]; e=em_estimates(gs,40)
        bo[b]={k:dict(p=float(e[k][0]),n_sets=int(e[k][1])) for k in e}
    res['em_by_best_of']=bo
    # (3) Markov
    mk={}
    for pt in (0.60,0.627,0.66): mk[f'equal_pt{pt}']=dict(hold=round(game_hold(pt),4),P_set_first_server=round(set_win_first_server(pt,pt),4))
    mk['unequal(+/-.02 pts)']=dict(stronger_serves_first=round(set_win_first_server(.647,.607),4),weaker_serves_first=round(set_win_first_server(.607,.647),4))
    mk['unequal(+/-.04 pts)']=dict(stronger_serves_first=round(set_win_first_server(.667,.587),4),weaker_serves_first=round(set_win_first_server(.587,.667),4))
    res['markov']=mk
    # (4) simulation validation
    g,t=sim_matches(100000,m=res['avg_serve_point_win'])
    e=em_estimates(g,40); acc=defaultdict(list)
    for bo_,b,sf_,seq,F in g:
        if F is None: continue
        p=0
        for j,(a,bb,tb) in enumerate(seq):
            firstA=((p%2==0)==(F=='A')); acc['first_set' if j==0 else 'later'].append(firstA==(a>bb)); p+=ngames((a,bb,tb))
    res['sim_validation']=dict(truth={k:float(v) for k,v in t.items()},em={k:float(v[0]) for k,v in e.items()},naive={k:float(np.mean(v)) for k,v in acc.items()},ident_frac=float(np.mean([x[4] is not None for x in g])))
    json.dump(res,open(OUT+'/results.json','w'),indent=1,default=float)
    print(json.dumps(res,indent=1,default=float))
