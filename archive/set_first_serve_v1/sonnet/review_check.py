import analysis as A, numpy as np
d=A.load(); rows,val=A.build(d)
def prep(rows,nb=8):
    ok=[r for r in rows if not(np.isnan(r[12]) or np.isnan(r[13]))]
    gaps=np.array([abs(r[12]-r[13]) for r in ok]); lvl=np.array([(r[12]+r[13])/2 for r in ok])
    e=np.quantile(gaps,np.linspace(0,1,nb+1)[1:-1]); g=[]
    for r in ok:
        year,surf,lvl_,bo,sets,N,first,wr,lr,wid,lid,amb,ws,ls=r
        Aw=ws>ls   # A = better in-match server (winner if higher rate)
        if ws==ls: continue
        b=int(np.searchsorted(e,abs(ws-ls)))
        seq=tuple((a,bb,tb) if Aw else (bb,a,tb) for a,bb,tb in sets)
        F=None if first is None else ('A' if (first=='w')==Aw else 'B')
        g.append((bo,b,surf,seq,F))
    return g
G=prep(rows); e=A.em_estimates(G,40)
print(len(G),{k:round(v[0],4) for k,v in e.items()})
for bo in (3,5):
    e=A.em_estimates([x for x in G if x[0]==bo],40); print(bo,{k:round(v[0],4) for k,v in e.items() if k in('first_set','later','all')})
g,t=A.sim_matches(60000); print(t)
