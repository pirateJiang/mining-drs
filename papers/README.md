> [!TODO]
> turn this into a papers page like i have in my RL library. for now its just notes.

NOTES: 
What is NPV, how is it used? 
What is a "strategic mine planning algorithm" 
    what does it operate on. what level of abstraction etc.
    he mentions algorithms in 2019_NavarraRojas

The paper states they are "limited in the degree of realism" because they treat unit operations (like the concentrator) as "black boxes" characterized solely by constant, time-averaged parameters (e.g., flat recovery rates or average milling costs).  
They use too little realism. Because they use time-averaged averages, they are blind to tactical, short-term phenomena like daily feed variation, equipment breakdowns, or dynamic surging. The time-averaged trends only show when modes are favored. This means a strategic plan might say "Use Mode A for Years 1-3 while mining the North pit, and Mode B for Years 4-6 for the South pit". However, it completely fails to describe the day-to-day or week-to-week dynamic conditions (like a sudden drop in a stockpile) that would force a temporary switch to a contingency mode.  

he says operational modes were black boxes characterized by time averaged data. is he saying they were basically just scalar values? and there was no notion of at this time this thing changes or that thing changes? 

Why can't time averaged describe the dynamic conditions that would trigger a change in. operational mode? 

im not understanding his specific example about this either. 

i need a better understanding of the case studies he mentions as someone who knows almost nothing about mining. and to better understand why these show what he is trying to show. 

Optimal functioning concentrator depend on "stable feed streems". Ore stockpiles are an attempt to minimize the effect of short term geological variation. or in other words, we save some ore so if we get less than expected we can used our saved ore. 

What is "blending" for stabalizing a concentrator. 

Mode changes are triggered by observed AND forecasted changes in stockpile levels (can ML be used for forecasting? again world models?)

how are these mode changes related to the RQ problem? 

Engineering KPIs: 
1. Operational Cost per Unit of Production (minimize this)
2. Throughput (maximize this)
3. Risk Aversion Metrics
    a. Customer Satisfaction

these can not be compared directly. 
This is where Pareto efficiency and Pareto Optimality comes in. 
    if an improvement in one objective leads to a degradation in any of the other objectives then it is Pareto Optimal. 

> [!TODO]
> what is the RL version of Pareto Optimiality? How can it be achieved with RL? 

Navarra mentioned recreating this Fig 2. plot of the Pareto frontier and tradeoff between operation cost per unit and customer satisfaction. 

> [!TODO]
> I should probably make the RQ problem in my DES system? maybe? or at least make a Gym Env for it and apply some RL algo to it (PPO as its continuous or even Stream AC).
> Deterministic and Stochastic and the 3rd more stochastic. 
> Then relate to this other stockpile problem (which i think is my current navarra example) that he talks about in the paper. 
>   he seems to mention productivity. how is this measured? i understand it semantically but dont actually see it in any of the plots. Where in the example we made do we see that A is more productive than B? Or Contingencies are respectively less productive? 
> The paper doesnt seem to include surging like our example had. 
> Problem formulation: Something like the RQ Problem but restocking takes time, in the form of a replenishment mode. There is stochasticity mostly in the inputs or stockpiles as opposed to traditional RQ where stochasticity is mainly in consumption. We must find a Critical threshold I_crit where we switch to replenishment mode and a Maximum threshold I_max where we switch to consumption mode. These can be linked loosely to R and Q (how?). Additionally the problem becomes slightly harder with variations. First being When we are allowed to switch modes, for example only in plant shutdowns, this simulates a delay in the mode change due to technical reasons (what are those reasons?). 
> Simplest formulation, maximize the throughput. Max Productivity, min stockpiles (stockpiles have an associated cost like in the RQ Problem).
> Mode A designed for 60/40 but now geostatistics and samples say the ratio will be 70/30 instead. (So goal is not necessarily to design a better Mode A or Mode B, but instead to improve our use of the modes). In this case Mode B is assumed to be just as good down stream, and is made for an 85/15 blend. We shouldn't design a single 70/30 split mode because geological uncertainty means our stockpiles are a random walk. If our Mode operates on the mean we don't have an easy way of controlling the stockpile values. Instead we have a Mode to affect each stockpile value and control the uncertainty from geological variation. This is similar to Options of feature atainment, though the motivations are different. Again only Mode A/Mode B switches during shutdowns. Make sure we have an example that matches this (Table 2 in pdf). Note a new assumption, that mining capacity exceeds the concentrator capacity, so the concentrator feed is the bottleneck. Also assumed that the mining method is inflexible (so stockpiles are needed). So total stockpile should stay for the most part constant (what is the mining speed in their contingency modes?). In A stockpile of Ore 1 Increases, in B stockpile of ore 2 increases. Total stays the same (roughly?). Decision of what mode is based on the stockpile levels. Mode decisions done during routine shutdowns (every 5 weeks). Assumptions are made so that stockouts only affect throughput (by entering contingency modes). Contingency modes are at least 1 day (contingency segement duration, where is that in my code?). 
> Does my ore generation match theres? They do the std as a percent, what is mine? a percent or raw value? 
> He uses t/h and not t/day 
> Recreate the curves like Fig 6, 7 and 8. 

> [!TODO]
> Make a not of where Table 3 is in our code (and the other tables and stuff).

Why do we need a consumption mode and a replenishment mode? Why not design the modes (or single Mode) so that it is balanced. 

He mentioned that the stock may continue to diminish after the mode switch due to stochasticity. How? is this just because of the case where randomly we dont get enough to replenish? 

> [!TODO]
> Make a helper for the deterministic two mode analysis? 
> Use those helper functions to recreate Eq2 to Eq5 and make a note/comment how these are a deterministic measure for the 2 Mode WHATS THE CASE case and that it can be used to determine the viability of modes. 

> [!TODO]
> An RL agent should learn the critical level and total stockpile level (is that I_max?). Again objective/reward is maximize throughput, minimize stockpile level.
> Compare to Random, Only A, Only B. Make a plot like Fig 5 with the Throughput vs the std of the geostatistic uncertainty. 
> Throughput uncertainty is another important metric (ie std of throughput)
> Compare with "naive" version too. 
> May want to do something like a fixed stockpile level, maximize throughput, and then vary the stockpile level. However it may be possible to have the agent choose both, OR do the opposite direction. for this method there is the additional question of different network weights for each stockpile level, including the stockpile level in the obs so the model can try and understand its constraints etc. 
> it would appear to me we could do threshold as in the paper, or have an RL agent (during the shutdown points etc) decide between Mode A and Mode B. 
> we should likely give all the information used in the equations for a fare comparison. 


> [!TODO]
> his future work. use this to somehow decide when you should mine what parts of the orebody to maximize throughput. becomes same as "what to stock" in your stockpiles problem with some constraints obviously. 
> i dont understand the ball one and the mill speed and addition rate one. i dont understand the mill throughput one. i dont understand the long term semi permanent adjustment one. i dont understand the grinding circuit and crush performance one. i dont understand the HPGR performance one. 



--- 

Notes on [APE1455294.pdf]

SGS is most common technique for Geostats on spatially distributed attributes, DRS is most basic for dynamic mass balance. 

First instance that combines SGS and DRS into a single framework. 

Inventory Stockpile (RQ problem) except that supply uncertainty comes from geostatistics. 

"Operating policies can be formulated and parameterised within the framework and tested against geological scenarios that are based on drill samples taken from the workface". TODO: what does this mean in my own words

Geostats and geological representation normally need 3 dimensions 

This paper seems to indicate that in many settings what we mine *can* be used to stabalize the stockpiles (something i think i suggested to navarra and jiang but was told that was already decided, maybe thats because it was in the context of fleet management). However in the scenario in the paper, this is not relevant as the ore basically has one way of mining it. So stockpiles must be used and operating modes. 

TODO: LOOK AT CITATIONS 7 and 10 WHICH USE ML ON DRS

Lots to understand about the specific scenario, why it can be reduced to 2D etc

New KPIs 
Cyanide Consumption
Throughput 