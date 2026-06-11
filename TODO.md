Im curious if it could be better to define my transitions as start conditions and end conditions, or somehow have that ability to more easily allow for action masking when using my DRS in a Gym Env and training an RL agent to select the operational mode on a day by day or campaign by campaign basis. 

Is it good practice to have the environment handle the end conditions? Or should that be done in my Controller DRS? I'm not sure if that makes sense. But my intuition says that it should be the controller, but i also sense from a DRS perspective there are not fixed timesteps.

Do you think that Modes are important enough that instead of using an Enum we could make a new class? My thought is right now modes are just Enums, but if we are adding start conditions, end conditions, and then also like the actual operation logic for each mode. it might make sense to say this is Mode A it can start if these conditions are met, it ends when this condition is met, and it does this.

The one thing is it should still be easy to do what I have done here where like the mode is preempted or like for the mode to switch from Mode A to Mode A Contingency and stuff.

Is a Mode Class PyTorch like in nature? Is it okay that it isn't even though my goal was a PyTorch like system for DRS?

RENAME PAPERS LIKE I DID WITH RL!

LOOK AT CITATIONS 7 and 10 WHICH USE ML ON DRS of APE1455294.pdf

Need to make Kriging stuff (or find online or in a library), SGS and GSGS stuff (or find in a library), and SIS stuff 

LOOK AT CITATION 11 TO GET ADD NPV AND IRR TO MY EXISTING MODELS AND PLOTS APE1455294.pdf

Make it possible to from code make a set of equations and variable valuables. 