# Have aces, breaks of serve and winners changed over the years?

**Short answer:** Aces rose for years and have stayed level since the mid-2010s, at about 4 per 100 serve points for women and 8 for men. Breaks of serve have slowly become rarer: for women from 37 to 34 per 100 return games since 2009, and for men from 25 to 20 since 1991. At the Grand Slams, winners (not counting aces) showed no clear change until about 2016 and have fallen by 1–2 per 100 points per decade since, most clearly at Wimbledon.

## Aces: a long rise, then a plateau

![Aces per 100 serve points by year and surface, for the women's tour from 2009, the men's tour from 1991 and the Challenger tour from 2010](figures/fig1_aces_by_surface.png)

Men's aces rose quickly in the 1990s. Comparing each tournament with itself, they went from about 5 per 100 serve points in 1991 to about 7 in 1997, then crept up to about 8 by 2014–15. Since then they have stayed level, at about 8. Women's aces rose more gently, from about 3.3 per 100 serve points in 2009 to 4 in 2015, and have stayed at about 4 since. On the Challenger tour, aces have not changed since 2010 (about 6).

The surface matters more than the year. Aces are most common on grass and hard courts and least common on clay: a men's grass-court match has nearly twice the aces of a clay-court one.

The open markers are 2026, a season still in progress.

## Breaks of serve: slowly becoming rarer

![Breaks of serve per 100 return games by year and surface, for the women's, men's and Challenger tours](figures/fig2_breaks_by_surface.png)

Breaks of serve have been getting slowly rarer for a long time.

- **Men:** servers were broken in 25 of every 100 return games in 1991, 21 in 2016 and 20 in 2025. The decline was fastest before the mid-2010s and has slowed since. In the last ten seasons it continued only on hard courts, by about 1 point per decade.
- **Women:** servers were broken in 37 of every 100 return games in 2009 and 34 in 2025, a steady fall of about 1.5 points per decade. It comes from hard courts, where breaks fell by about 3 points per decade; clay and grass show no clear change.
- **Challenger:** no change since 2010.

These trends hold when each tournament is compared only with itself, so they are not caused by changes in the tournament calendar.

## Winners: no clear change, then edging down at the Slams

![Winners excluding aces per 100 points at the Grand Slams, by year and surface, for women and men, 2011–2024](figures/fig3_winners_slams.png)

About a quarter of Slam points end in a winner (not counting aces): 26% for women and 25% for men. That share showed no clear change from 2011 to about 2016 and has fallen by 1–2 points per decade since.

The fall is not the same at every Slam. It is clearest at Wimbledon, for women and men alike, and for men also at the Australian Open, although the Australian Open's data came from a different provider in 2018–21, so part of that decline may reflect how winners were recorded. For women it is mainly a Wimbledon change: the other three Slams show no clear change. Wimbledon's point data come from the same source every year, so this is not a switch of data feed.

The clay line ends in 2021 because the source has no French Open (or Australian Open) point data after that year.

One apparent change is not real. The volunteer-charted Match Charting Project seems to show men's winners rising sharply after 2021. That is because one prolific volunteer charter records far more winners than others and charted a large share of recent matches. Without that person's matches, the rate is flat.

## What this does and doesn't show

- **The changes are small next to the gaps** between surfaces and between the women's and men's tours.
- **We report many trends.** A few that look significant are expected by chance. The consistent findings are the plateau in aces, the long decline in breaks and the recent decline in Slam winners.
- **"No change" means not detected.** Where the intervals are wide, for example on grass, a small change cannot be ruled out.
- **The years covered differ by tour** because serve statistics are only complete from 1991 for men, 2009 for women and 2010 for the Challenger tour. Slam point data start in 2011.
- **2020 was unusual,** with fewer events and no Wimbledon.
- **Slam data come from two sources.** The Australian Open and French Open used a different provider in 2018–21 and are missing after 2021. The method allows for this.
- **Match Charting is a volunteer sample.** It is fine for levels at the Slams, but not for trends outside them.

## Data

- **Tour and Challenger matches** (men 1991–2026, women 2009–2026, Challenger 2010–2026): [TennisMyLife](https://stats.tennismylife.org) (no stated licence; credit given). The women's part follows Sackmann's `tennis_wta` format (CC BY-NC-SA 4.0).
- **Grand Slam point-by-point, 2011–24:** Jeff Sackmann / Tennis Abstract, `tennis_slam_pointbypoint`, via the fork [byshiny/tennis_slam_pointbypoint](https://github.com/byshiny/tennis_slam_pointbypoint) at commit `6febb77`. Licence: [CC BY-NC-SA 4.0](http://creativecommons.org/licenses/by-nc-sa/4.0/).
- **Match Charting Project, 2016–26:** Jeff Sackmann, [tennis_MatchChartingProject](https://github.com/JeffSackmann/tennis_MatchChartingProject) at commit `1813a13`. Licence: CC BY-NC-SA 4.0.

## More detail

- [METHODS.md](METHODS.md) has the cleaning steps, models, robustness checks, full tables and appendix figures.
- This analysis was independently cross-reviewed by a second agent, and the fixes were verified.

## Reproduce

```bash
make serve_return_trends
```
