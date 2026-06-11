General DRS not just mining
Components in drs/ are not mining specific 
Efficient
Python first, coding should be simple, fast, easy to read, and feel like Python (or at least like PyTorch) where possible. 
Secondarily, it should be possible to create drs simulators/simulations using a drag and drop Visual approach like Arena. 
It should be possible to go from Python to Visual and Visual to Python. 
Improve on Arena by allowing DRS natively. Instead of needing a pointer entity or needing to use several assigns etc to do the rates, modules etc should be generally semantic. A plant module, a fleet module, a mine module, stockpile module.
It should probably be possible to have a module use modules (like PyTorch), so that its possible to increase the detail on each of the components. ie we could have a simple fleet that just provides what is needed according to the Mode of Operation. We could then make that fleet module more detailed, with for example several trucks (possibly each represented by their own modules etc)
Based on Navarras work, so operating modes are important. 
Using a simple Gym Wrapper it should be possible to make a Gym Env using this. 
In some form the PyTorch of DRS
Possible to make and understand something easily visually. Possibly limited. However, in python mostly anything should be possible.
Maybe visually levels of abstractions? Ability to zoom into a module and see its internal modules or something
Should attempt to be some form of a bridge between programmers and mining or any non programmers. A non programmer can make a simple version using the visual system and hand it off to the programmer to do things like RL or Linear Programming etc. 
Should run FAST if possible, faster the better. 
Fail fast! Errors should be caught 
Visual system should represent how system runs, so that it can be visually debugged and tweaked to make semantic sense. 
Visual mode should allow us to see flow and different operating modes. 
Ability to make components or custom drs.Modules visually (ie make things like our Stockpile class or our ConcentratorPlant using the visual system)
Efficient Parallel Execution for MonteCarlo Results
Minimal boilerplate for most cases. ie i dont want to have to register all edges manually, or all variables. Like it shouldnt feel like i am saying track this in our graph, track that in our graph. Or these kind of things. For the python approach it should feel very native, like PyTorch does, where you barely think about how the gradients are tracked etc. 
Avoid hacky heuristics like using the naming of a variable or things like that to determine if its an inflow or outflow, or things like "industrial semantics" like saying things flow towards the plant, or other things like that. These are not robust. 
Abstract the DRS logic. Generally speaking, we dont want users to think about how they are updating the rates or anything like that. They should think about what they want to model. This is my concentrator, it needs this much or, it outputs this much. Here is the function to transform it. This is my fleet, it moves this much. Not something like finding the threshold. The goal is that someone from Mining or Finance or whatever, not someone familiar with DRS systems, can pick this up, model a Mine as you would normally, saying here is my Mine, here is my fleet, here is my stockpiles, here is my concentrator, then define the internals, and it runs. 
i think fundamentally sometimes users dont want tensors to be tracked wheras in our case we always want to the translation from visual to python and python to visual to work. meaning it needs to track everything. 

--- 
Mining Specific? 
Allow for passing of more than just mass, like cyanide use for example 
Dynamic mass balance support or enforcement?
Allow for stochasticity everywhere. For mining this is OreGeneration, but also fleets, drive times, etc. 
Bridge the gap between Navarra and Ruossos? 
Allow for SGS etc
Allow for fleet management
Allow for custom metrics like NPV etc. 
Delays for operating changes, travel of ore and resources, etc.
Prevention of incorrect edges or connections? mass flowing into grade? is this overstepping? Does this add to much boilerplate to the pythonic pytorch approach?
Sensors and uncertainty. Is this mining specific or useful to any DRS? Are these edges or nodes? etc?
Another goal would be like an OpenAI gym for Mining Optimization. Or in other words a set of basic, simple, fast, solvable problems to test mining optimization methods on several types of mines and types of optimization problems. ie a set of reusable and expandable scenarios. like cartpole or mountain car.
In future we can add a warning for order of execution not matching topoligical order leading to possible 1 tick delays

--- 

Current Plan: 
1. Data Types like Resource, Observation, Control OR just a generic Data type, then Data stores what objects its been used on or functions its been used in some how. ie it stores where it has travelled, and so we can make sort of a path for the data if that makes sense. 
    a. Do these fit into all the possible DRS systems
    b. how do we handle branching so that all paths appear in our graph? (and in case of random events etc appear correctly).
    c. is there a way that data we can track the path of data without having to do the somewhat unintuitive thing that modules return data. I feel intuitive to drs systems is that your levels are updated by rates. And this should be implicit. I think its possibly unintuitive when making a drs system to not think about levels and rates. But maybe its better to use the DRS system totally in the background, and instead you build it naturally somehow thinking about flow. Tonnes in and tonnes out or whatever. and it does that. But its also unintuitive to say X produces Ore, ore is passed to Y. because X may be producing ore in a consistent continuous stream. And so what would be the "time interval" for the ore? I'm not sure if that makes sense, but in the current system X does not produce ore, X sets the rate of the ore level to +1000 and that continuous updates the ore level.  
2. Register children with __setattr__ like pytorch so that discover of child modules and variables works without needing to manually register.
3. Graph nodes should emerge from behaviour, as should connections ideally. Something should have to happen or be used for a connection to emerge. 
4. A drs.Module that represents a block in the visualization (or a subblock i guess, as any drs block can be a drs (is that true?))? 
5. 

Explicit connections is bad, as the connections may not match logic, adds boilerplate, and is more work to set up. In the visual case explicit connections tend to mean something happens

I dont want to have to register like the nodes or whatever or children and all that for tracking. I know we could do explicit connections but as I mention below I worry about the boilerplate of that, and I also feel it turns our system into creating graphs with code instead of the PyTorch feeling, though maybe creating graphs with code is the best approach im not sure. Additionally, although update_rates is like our pytorch forward, pytorch is also able to track gradients on other methods and stuff right? Like i guess i also want to be able to visualize for modules that have other custom functions too, like our fleet or controllers or other that may update stuff in a custom function. I'm not sure if a want something like pytorches add_module or register_buffer as i think those are generally not to common, but in this case it feels a little more common and so avoiding that kind of boilerplate would be ideal if possible (though it may not be or may be worse if it is avoided and so should be done like pytorchs register_buffer, if that is the case just let me know and let me know why)

Another thing is that probably the top module (the ConcentratorModel) should not be a node. like it is kind of just a container for the other nodes. There are or may in the future be other cases of this, like if i improve the fleet. I dont really want to add an "is_container" flag as i think that adds boiler plate and again feels un pytorchy. also it might get annoying to be like oh i forgot to mark it as a container (which is purely cosmetic if that makes sense, but visually and semantically important)

For this "generic Signal or RateVector class in the core, or simply allow variables to pass dictionaries of rates." Which is better or worse? Like what are pros and cons? 
For signals vs RateVectors im not sure what i want to go with, in some ways i feel a "signal" or something like that or lets say something like an Arena "output" is important (like a stat or metric) and maybe worth its own type, but in another way im not sure if its too rigid, and if its nicer to go with the dictionary approach. Also something like VectorLevel or VectorRate might allow me to explicity track individual levels rates (or something, but what is that useful for anyways?). I might need to see a sample code approach for both methods or versions. 
Do I need this at all? Can i not just pass in multiple rates and levels that are individual, no dict needed?

Also for the OreParcel and stuff is it possible to generalize it for DRS? perhaps there is something "abstract" here, something like a DataGenerator something? Almost like a pytorch DataLoader or DataSet. How can this be generalized to DRS?

I am weighing the pros and cons of the Port approach. InputPorts and OutputPorts I know would work well probably, but i worry it adds boilerplate and it feels "un pytonic" or at least not very pytorch like. I'm wondering if there is a better way or another way or if that is the best? What are some other options? What are some pros and cons? 
I think the pytorch functional connections approach could be very interesting, though im not sure how this would translate for a DRS as what does the "call" return? in pytorch this is simple it returns the output of the network (a tensor) in our case its unclear i think, and this has to be figured out, though if it allows for better tracing and graphing and implicit connections and a better code experience I like it. How are assignments handled? 
For the explicit connectors approach first how do we enforce that every class define these. Second should every class define these? How do we make sure not to use heuristics like the variables name that stores inflows or outflows? How do we make sure that theres not too much boiler plate or that we arent just basically manually creating this mermaid graph with python (which i feel is not really the goal in my opinion). How can i correctly get the direction of these components? How can I know if plant.rate is being set or being used (or both?) How do i know the "direction" of the information or physical stuff flow. Generally speaking if its possible to do
plant.ore_1_useage = mode_a.ore_1_usage or self.plant.inflow = self.fleet.outflow or something that would be nice and simple, but can everything work with that approach? (also it should be generic and not use/require the semantic knowledge that inflow is always used as an input to other nodes etc). 
How does pytorch handle the assignment? Like if in a module you say module.x = submodule.y it still kind of works i feel like, or am I wrong? Like would that solution used in pytorch not be applicable here? 
I'm also aware that we can do some kind of bind method that binds one variable to another. this feels less than ideal though may be necessary. overall i would hope we could kind of bind dynamically, seeing that it happens in the code without having to explicitly bind. I'm not sure if binding goes hand in hand with the functional approach or not either, or where it falls. I think in general the functional approach suffers from the fact that most update rates probably modify the state and dont return a value. Maybe there is a better library made for this kind of stuff that i can base my solution on? What are 3-5 other libraries or systems or ways of doing this more related to DRS that might be better? 

It may also be possible to use execution contexts, but since in general id like the visualization etc to happen implicity or kind of natively i think it would be annoying to define an execution context in all my modules or stuff that needs to be tracked (which is kind of everything)

additionally i think it could be possible to somehow use an override or something of __set__ but im not sure of the details or pros and cons. 

Id like more detail on something like a Jax approach or a functional approach and how that might work? What might the code look like etc. Pros and cons

Id also like detail on something like a SystemC solution or Modelica. 

Looking at Jax, SystemC, and Modelica, and Arena, what are some pros and cons. How are they suited or not suited to DRS systems. What makes them better than the system i have created so far? How can I incorporate these into my goals?

--- 


Why do I even need all this tracing, network, visualization stuff? I already made a drs.Module with Variables and Levels and Timers and stuff like that and it gets executed correctly by a drs runner class and like forward you have an update_rates where you update your rates and the runner updates your levels correctly of all your modules. I have ore generators which allow for that data source abstraction. I have Modes as a first class thing, that basically each mode has a set of rates, and the controller checks what mode we are in and sets the rates. Maybe that could be cleaned up I guess. But its not too bad right now each Mode has start conditions, end conditions, and dynmaics, so the controller just kind of checks if the start and end conditions are met, sets the rates using apply_dynamics, and then selects the Mode to switch to if that makes sense. So controller defines transitions but modes define what happens in that mode. And the controller is just a drs.Module. I've got simple telemetry that basically just stores a history of drs.State and drs.Variables and stuff. Honestly its alright, it does its job but maybe could be cleaner or better. 
Overall its pretty nice i think.

It works and it does its job. My trouble is not that. Like it does its job and its Pythonic or Pytorchy. 

The trouble is really two things i think sort of. One its a bit hard to read, not to hard but a little. And basically i think theres nothing stopping incorrect usage (i could be wrong but yeah). 

The other is that it requires knowledge of Python and PyTorch a little, or at least conventions of those. Its nicer than Arena, you don't need to code all the rate and level logic, you just kind of make almost config that just say what to set rates to depending on stuff and the drs rate logic is handled. BUT its still a bit messy. Like its a lot of jumping around. its a lot of accessing the rates or levels and stuff of other objects. Like the rate of the fleet is the rate of the concentrator use. But there is a question, where does that get set? In the fleet in the controller? in the concentrator? Anywhere else? those are all possible and maybe thats good as it gives the freedom of pytorch. But visualization would be nice. It would allow us to see how that is happening, and see that oh the concentrator is setting the fleet flow rate, that doesnt really make sense. And I want visually because I think the people I work with Jiang, Navarra, etc would be much more interested in adopting it more widely if they could use a visual builder instead of a Pythonic one. Most people (i think) that use drs for their jobs are not great programmers, they dont want to do it in Python. Thats why Arena is often used. Its drag and drop. My system right now also has some extra repetitive work for things like mass balance etc. You can really just say set the rate to X, or like enter mode B. You need to then say well okay for mass balance fleet rate changes to X - Y and this goes to Y + this and that and then its like you changed one rate but had to do 10 things. In my simple situation its an ore face, 2 stockpiles, and a concentrator. But its about 400 lines. We have our Modes. But its really the most of the logic should be in the modes. Instead there is a lot to make sure all the rates are correctly set. But it should really be Concentrator in this mode uses this much, in this case we want our fleet to replace that much ore, donzo (we have 2 types of ore so the ratio of ore 1 to 2 changes but still). 

Honestly, function is the most important. And the freedom to make any DRS. 

I think the visual style also in my mind might make for better abstraction. You get to say here is my plant, here is my fleet, here are my stockpiles. You connect them together. Like that is nice. When I first roughly visualized my system I got a very similar graph to when me and Jiang were planning. And I felt like oh this is so much nicer than looking through all the code and components. Maybe thats because of bad code deisng and stuff but im not sure. And i also saw that and though we are doing all this planning to add fleets but when I visualize it fleets are a single node, with some basic internals, that swap out our existing simpler fleet that just routes whatever the plant needs. So its like wait this is the level people think about when actually planning. Not rates and levels. They think like this: 

--- 
The route policy in our visualization doesnt seem true to our current system at the moment. At the moment the trucks do or at least should know what the parcel is and use that to always route ore 1 to stockpile 1 and ore 2 to stockpile 2. 
Then the way i think about it the controller looks at the stockpiles and decides which stockpiles to pull from and how much. 
Also sensor logic the inputs vs outputs could maybe be more clear? like i feel like the true ones are all inputs and the outputs are all the belief ones. And maybe theres a way to show that mapping. 
The concept of grade could also be improved as that word kind of means something else. 
also the controller tooltip is so hard to read 

1. Get dynamic mass balance working with multiple muck sites to a single concentrator/crusher
2. Consider different feed rates from muck sites to our stockpiles (which go to our concentrators)
3. maximize the daily tonnage time average (maximize daily throughput)
4. add stochastic drive times
5. add a conveyor and make parcel additions to stockpile gradual

Start with unlimited quantities of ore at each of the faces
the faces have different distances and different grades of ore (one has more ore 1 and one has more ore 2)

parcels always the same size 
parcel grade stays same for each muck site
different tonnage per muck site
trucks/parcels have limited capacity (smaller than the tonnes of the muck site)
lower level faces are always slower also to send ore to the same stockpile. trucks have to drive all the way to the surface or there is a skip. assume no elevator or skip for now.

MAYBE START WITH SCENARIO 2 
goal 1: increase time in mode A and reduce contingencies 
goal 2: keep ratio of stockpile roughly 60% Ore 1 and 40% Ore 2

Goal Remake Fig 6 with Fleet Management added to Mode A and Mode B and have a higher throughput (especially on lower target stockpile size). [!2019_NavarraRojas paper]

BASE SCENARIO. CONCENTRATOR WORKS FOR EXPECTED GEO STATS.
TIMELINE 1: 

No matter what Shutdown 1 day long every 34 Days.
Ore 2 is Valuable Ore
Parcel is random 60% Ore 1 40% Ore 2

We don't want any Mode A Contingency
Geostats will cause uncertainty leading to stockouts if no fleet management (by random chance). For example, if you suddenly get many high Ore 1 parcels you will run out of Ore 2 and enter Mode A Contingency.  

With fleet management, when Ore 2 is low we utilize the fleet on more High Ore 2 faces leading to more Ore 2 in the parcels and so Ore 2 stockpile does not decrease despite unfavorable geo statistics. 

Mode A (Normal Operating Mode):
    Concentrator 6000 t/d
    Input to Concentrator 60% Ore 1 40% Ore 2
    Moderate or high usage of fleet
    Balanced Faces for Ore 1 and Ore 2

Mode A Contingency (Process as much Ore 1 as possible):
    3900 t/d 
    Input to Concentrator 100% Ore 1
    Low usage of fleet on Ore 1 and high usage of fleet on Ore 2


---- 

TIMELINE 2:

MODE B LATER WHEN GEO STATS CHANGE. 

Mode B (Recuperating Operating Mode):
    Concentrator 5400 t/d
    Input to Concentrator 85% Ore 1 15% Ore 2
    Fleet Mine X% High Ore 1 Grade Y% Low Ore 1 Grade
    Moderate or high usage of fleet


Mode B Contingency (Process as much Ore 2 as possible):
    2500 t/d 
    Input to Concentrator 100% Ore 2
    Low useage of fleet
    Low usage of fleet on Ore 2 and high usage of fleet on Ore 1


                                    Ore 1 Stockpile
                                   /               \
             Parcels ===Conveyor===                 ===Conveyor=== Concentrator
                |    Ore 2         \               /
                |--- Face 2         Ore 2 Stockpile
    Ore 1       |    15/85
    Face 1 -----|    1 hour
    45/55
    2 hours


---
QUESTIONS: 
should we try to always have 60/40 Ratio in our stockpiles? 


HOW WOULD RUOUSSOS DO THIS? HE HAD HIS FLEET MANAGEMENT OPTIMIZATION PAPER.
--- 

They dont think about rates and levels. And i think that would be powerful. A drs system where you dont (as much as possible or desired) need to think about rates and levels. DRS is a tool I feel, but not necessarily the end goal. The end goal is a simulation of a mine or other system. And so what users and people want to see is that mine or system. They dont want to say here are my rates and levels. They want to see the system. And Navarra has just chosen to use a DRS to simulate this system. But in reality most industrial software does not use a DRS. It uses a nicer more complex but semantic system. We see the trucks and the mine sites and its all 3D. And like imagine if we could allow for that design process, that level of abstraction, and then with some work, you click RUN and it runs your DRS one the system you set up. I'm not sure what they use these systems for exactly. I think for human based mine planning so that they can see the state of the mine. I also think the argument can be made that if the drs system we/i make can not do what those industrial ones do, then the research is not useful, as it is not capable of simulating what the industrial systems do. And on top of that it should hopefully be conceptually easy. 

--- 
This syntax is potentially nice, though the explicit routing is not ideal but maybe it makes things cleaner and less bug prone: 
# The user defines the SEMANTIC components, not the math.
face1 = MineFace(name="Face 1", capacity=10000, ore_ratio={"ore1": 0.45, "ore2": 0.55})
face2 = MineFace(name="Face 2", capacity=10000, ore_ratio={"ore1": 0.15, "ore2": 0.85})

stock1 = Stockpile(name="Ore 1 Stock", expected_type="ore1")
stock2 = Stockpile(name="Ore 2 Stock", expected_type="ore2")

mill = Concentrator(name="Navarra Mill")

# The user explicitly routes the physical flow (This maps 1:1 to drawing a line in a UI)
# The framework automatically handles the variable registration and rate conservation!
network = DRSNetwork()
network.connect(source=face1, target=stock1, via="fleet", route_filter="ore1")
network.connect(source=face1, target=stock2, via="fleet", route_filter="ore2")
# ... connections for face 2 ...
network.connect(source=[stock1, stock2], target=mill)

# The user applies the logic (Modes) on top of the physical network
controller = ModeController(mill=mill, fleet=fleet)
controller.add_mode("Mode A", target_throughput=6000, target_ratio={"ore1": 0.60, "ore2": 0.40})
controller.add_mode("Mode A Contingency", target_throughput=3900, target_ratio={"ore1": 1.0, "ore2": 0.0})

---

I am not sold on this possible solution and would like to see how other methods look for the same thing. Additionally there is something I don't want that I see suggested often. A network for physical stuff and then separately the Modules for logic and things like that. This i think creates two systems to keep track of instead of one. The idea is that you have your network of physical stuff. The controller and sensors and stuff are not network nodes but just modules. 1 this becomes hard to visualize. It works nicely and makes all the physical stuff simpler. But I have myself constantly asking why not make everything a Node and Edge. Like the controller is a Node that doesnt take in any physical stuff but it takes in information. And like I just think its messy to have these two systems. Because yes I could define my physical system with the nodes and edges but then the other parts feel clunky and visualization breaks down. It also has me wondering if there is a better way to do the Controller and the Sensors and stuff. Right now these are not part of the core library. They are made using the core library. Are these things inherint or useful to any DRS simulator? I'm not 100% sure they are, but i almost feel that like something like a sensor could be its own network or take in a network or something and it says heres what nodes and values i sense from the network list and how. But i'm not sure how this could be done or if it should be done this way or if instead each node should output true and sensor values or if simply as I am doing we have a sensor module that reads the internals of things it wants to sense. But this may be tangential to the core problem. 

--- 
Something like this might be good (i think its what i have) i have as its not that made for the user to say this is a level this is a variable. Also why do we need to intercept __setattr__ if doing this? I almost wonder if we should define a Rate class as well. 

class NavarraMill(drs.Module):
    def __init__(self):
        super().__init__()
        self.capacity = drs.Variable(6000)
        self.ore_level = drs.Level()
        
    def update_rates(self):
        # We just write the logic. 
        # The framework implicitly builds the graph under the hood!
        self.ore_level.rate = self.inflow.rate - self.capacity

--- 

Something maybe important (im not 100% sure) i think there (at least right now) always needs to be a top level drs.Module which is passed in to our excecutor. How can we use this? Is this a way to stop assignments from breaking our variables history tapes (if we go with variable history tapes).

Also do I want to do the rate = inflow - outflow type thing? Is this nicer? And user defines inflow and outflow. Does this work cleanly in all scenarios? Is this what we already do? 

--- 

Here is another option for code. It is overall nice, but there is the interesting thing that Nodes or Modules transform some kind of data or input and output it. We are no longer modifying a state, but more like the parcels that are being passed. It may be nice for planning to say like what happens to an ore parcel going through our system. But there are some questions with how this relates to rates and flows. What will a user define, how will they do it? Conceptually a "rate" does not really relate to any specific parcel but this coding style feels like it does. Maybe though instead of thinking in parcels we think in flows: 

import drs

class NavarraSystem(drs.Module):
    def __init__(self):
        super().__init__()
        # 1. Automatic Discovery via __setattr__
        # Just like PyTorch nn.Module, assigning these registers them to the graph hierarchy.
        self.face1 = MineFace(capacity=10000, grade={"ore1": 0.45, "ore2": 0.55})
        self.face2 = MineFace(capacity=10000, grade={"ore1": 0.15, "ore2": 0.85})
        self.fleet = Fleet()
        
        self.stock1 = Stockpile(name="Ore 1")
        self.stock2 = Stockpile(name="Ore 2")
        self.mill = Concentrator(max_capacity=6000)
        
        self.sensor = TelemetrySensor()
        self.controller = ModeController()

    def forward(self):
        # 2. Emergent Connections (The Graph draws itself here)
        
        # SENSORS: Observe the physical world, output Information Signals
        stock_info = self.sensor(self.stock1.level, self.stock2.level)
        
        # CONTROLLER: Evaluate Information, output Command Signals
        mode = self.controller(stock_info)
        
        # MINE: Produce physical flows based on commands
        f1_rate = self.face1(mode)
        f2_rate = self.face2(mode)
        
        # FLEET: Route the raw rates into specific stockpile rates
        ore1_rate, ore2_rate = self.fleet(f1_rate, f2_rate, mode)
        
        # STOCKPILES: Receive flows, update levels, output available downstream rates
        s1_out = self.stock1(ore1_rate)
        s2_out = self.stock2(ore2_rate)
        
        # MILL: Consume the final rates
        self.mill(s1_out, s2_out, mode)

# To run the simulation:
model = NavarraSystem()
engine = drs.Engine(model)
engine.run(days=365)

--- 

Arguably sensors could be seen as nodes. 

It has been suggested that:
"Data Types like Resource, Observation, Control OR just a generic Data type?"
Use a single, generic drs.Signal object under the hood.

Python
class Signal:
    def __init__(self, value, attributes=None, source_module=None):
        self.value = value
        self.attributes = attributes or {}
        self.source_module = source_module

"You don't need strict types. The "type" of the signal is naturally implied by the module that emitted it. A physical flow signal just happens to have attributes={"mass": 1000, "grade": 0.45}, while a command signal has attributes={"command": "MODE_B"}. This keeps the backend minimal and perfectly generalizable beyond mining."

Is this similar to our existing Variable class? 

--- 

To preserve the graph for your visualization engine without adding boilerplate, your users must be able to write native-looking math, and your Variable classes must intercept it using Python's magic methods (__add__, __sub__, __mul__, etc.).

Something like this: 
The User Experience:
Python
def update_rates(self):
    # No .value! Operators are overloaded to track dependencies implicitly.
    self.current_extraction_rate = self.config.mode_a_ore1 + self.config.mode_a_ore2
    
    self.ore_extracted.rate = self.current_extraction_rate
    self.ore_stock.rate = self.current_extraction_rate - 1000
The Framework Implementation (variables.py modification):
Python
class Variable:
    def __init__(self, name: str, initial_value: float = 0.0):
        self.name = name
        self.value = initial_value

    # Overload operators to return an "Expression" or track connections
    def __sub__(self, other):
        if isinstance(other, Variable):
            return Expression(operator="-", left=self, right=other)
        elif isinstance(other, (int, float)):
            return Expression(operator="-", left=self, right=Constant(other))
        return NotImplemented

When self.ore_stock.rate receives an Expression object instead of a raw float, your __setattr__ hooks can immediately log: “Node current_extraction_rate links to Node ore_stock via a subtraction operation.” Your visual graph generates itself entirely from the math.

By combining your Level + Auxiliary architecture with implicit tracing, you can build highly semantic components for your industrial users (like Navarra or Jiang) that hide the underlying math entirely.

A domain expert can define a high-level model using clean, declarative blocks:

Python
class ConcentratorPlant(drs.Module):
    def __init__(self, config):
        super().__init__()
        # Semantic components - everything is a Node/Variable underneath
        self.stockpile = drs.Level("OreStockpile", initial_value=config.target_stock)
        self.mill_consumption = drs.Auxiliary("MillConsumption")

    def set_operating_mode(self, throughput: float):
        # The logic states what it wants to happen
        self.mill_consumption = throughput
        self.stockpile.rate = self.incoming_flow - self.mill_consumption

This is using Auxillary or something like that instead of a Rate type. The variable types still have to be brainstormed. Perhaps we want a Rate type still? Auxillary feels like it might get confused with Variable. Level and Timer are clear what they are. But Variable and Auxillary seem a bit too similar semantically, could we fuse them? 

Consider removing other drs types and just having Variable and Level. Rates, constants, states, etc can be seen as variables. And then Levels have rates (which are a drs.Variable). Also possibly add a drs.Flow though this may not be needed. Its basically an edge. if drs.Module is a node. 

A better more detailed formulation is this: 
You need to split your classes into two families: Continuous (Variables, Levels, Timers) and Categorical (States). We will have to streamline our existing implementation including removing the @property interceptions, making only levels have rates (not all variables), removing the excecution tracer hooks. Some benefits are: If a user writes self.stockpile = drs.Variable(), and later tries to write self.stockpile.rate = 50, Python will crash with an AttributeError. They are forced to use drs.Level() for things that flow, satisfying your "Fail Fast" requirement. Because Variable.value checks if it holds an Expression, a user can now write:
self.total_mass = drs.Variable("Total Mass")
self.total_mass.value = self.stock1 + self.stock2
Whenever self.total_mass.value is read, it instantly evaluates the AST. No manual updating required!

--- 

A suggested combination of the two above methods might be: 
import drs

# --- THE MICRO LEVEL (Math and Physics) ---
class Stockpile(drs.Module):
    def __init__(self, name, initial_capacity):
        super().__init__()
        # drs.Level handles the dt integration in the background engine
        self.level = drs.Level(name, initial_value=initial_capacity)

    def forward(self, inflow_signal: drs.Signal, requested_outflow: drs.Signal) -> drs.Signal:
        # We calculate the actual outflow (preventing negative stock)
        actual_outflow_rate = min(self.level.value / drs.dt, requested_outflow.value)
        
        # We update our internal rate using pure math!
        self.level.rate = inflow_signal.value - actual_outflow_rate
        
        # We output the actual flow leaving the stockpile as a new Signal
        return drs.Signal(value=actual_outflow_rate, source_module=self)


# --- THE MACRO LEVEL (Semantic Factory Layout) ---
class NavarraSystem(drs.Module):
    def __init__(self):
        super().__init__()
        # __setattr__ auto-registers these!
        self.face1 = MineFace(capacity=10000)
        self.stock1 = Stockpile(name="Ore 1", initial_capacity=0)
        self.mill = Concentrator(max_capacity=6000)
        self.controller = ModeController()

    def forward(self):
        # 1. Controller outputs an Information/Command Signal
        mill_request = self.controller()
        
        # 2. Mine outputs a Physical Rate Signal
        raw_ore_flow = self.face1(mill_request)
        
        # 3. Stockpile absorbs the flow, and outputs what it can give
        available_ore = self.stock1(raw_ore_flow, requested_outflow=mill_request)
        
        # 4. Mill consumes the final flow
        self.mill(available_ore)

Some critiques are that it seems sometimes our drs.Module returns something, and sometimes it doesnt, which might be a little bit confusing. I also notice this uses signal. Is signal the same as our drs.Flow? is a drs.Flow a type of signal? 

An argument could be made that a module should always return what it produces, and if it produces nothing it returns None. My concern is about in place operations. How do we prevent users from messing up and destroying the calculation graph? Like what if they try and set the stockpile rate or level from the controller. I'm not sure if im explaining it but like what if instead of properly returning the flow/rate of what they produce they just do it internally and mess things up. How do we catch this correctly?

Also we are returning flows or signals. Which is fine. It looks alright not too much boilerplate. But why not do this at init time instead of run time if that makes sense. I guess the benefit is that the edges are based on actual computation. I think it also helps for branching and if statements. so dyanmic is the way to go.

We can try something like this to fix the issue of breaking the graph: 
Step 1: The __call__ Context Tracker
In your base drs.Module, you track who is currently executing.

Python
import threading

class ExecutionContext:
    _local = threading.local()
    
    @classmethod
    def get_current(cls):
        return getattr(cls._local, 'current_module', None)

    @classmethod
    def set_current(cls, module):
        cls._local.current_module = module

class Module:
    def __call__(self, *args, **kwargs):
        # 1. Remember who was executing before us
        previous = ExecutionContext.get_current()
        
        # 2. Set ourselves as the currently active module
        ExecutionContext.set_current(self)
        
        try:
            return self.forward(*args, **kwargs)
        finally:
            # 3. Restore the previous context
            ExecutionContext.set_current(previous)
Step 2: The Guardrail in Variable
Remember how __setattr__ registers children? When Stockpile creates self.level = drs.Level(), the __setattr__ sets level._owner = self.

Now, you just add one check to your Variable setters:

Python
class Variable:
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        current_actor = ExecutionContext.get_current()
        
        # GUARDRAIL: If someone is actively running, and it's not our owner...
        if current_actor is not None and current_actor is not self._owner:
            raise RuntimeError(
                f"Graph Destruction Error: '{current_actor.__class__.__name__}' "
                f"attempted to forcefully mutate '{self.name}', which is owned by "
                f"'{self._owner.__class__.__name__}'.\n"
                f"Modules must communicate by passing Signals/Flows. Do not mutate state directly!"
            )
            
        self._value = val
The Result: If an industrial engineer gets lazy and tries to write spaghetti code to hack the stockpile level directly from the controller, the simulation crashes instantly with a highly descriptive error. They are forced to write good, encapsulated code, which guarantees your graph will always be 100% accurate.

--- 

Variable / Level: This is the Memory (State). They belong to the Module (self.stockpile = drs.Level()).

Signal / Flow: This is the Message passed between modules during the forward() pass.

Recommendation: Do not use the word Signal. Call it drs.Flow. A Flow is just an ephemeral dataclass that carries the rates between modules during a single execution tick.

--- 

There is another problem of simply reading information not outputing it. For example controller only reads the stocklevels. how do we capture this? One way would be something like this: 
If the Controller just reads self.stockpile.level.value, the execution graph won't draw an "Information Edge" connecting them.

The Fix (The Observer Pattern):
Modules should pass Variable objects as inputs for information, just like they pass Flow objects for material.

Python
class ModeController(drs.Module):
    def forward(self, stock_level: drs.Variable):
        # We read the variable! The __get__ or operator overload can 
        # log that this Controller depends on this external Variable.
        if stock_level > 200: # <-- Overloaded __gt__ logs the edge!
            return drs.Flow(command="MODE_A")

In my opinion this has some serious problems. What if a user doesn't put stock levels in the args but instead ModeController has an attribute stockpile and then it does self.stockpile.value or something. This should also be valid if possible (thats a valid way and acceptible in pytorch).

--- 

We also need to solve this problem
The Dynamic Control Flow Trap (if / else)
You mentioned wanting it to be fast and wanting to trace the graph. There is a classic trap here that PyTorch and JAX both had to solve.
If you use standard Python if statements based on a drs.Variable in your forward() pass:

Python
if stock_level > 200:
    # Do something
Python will try to evaluate stock_level > 200 to a boolean True or False. But remember, we overloaded the operators to return an Expression AST! Python will crash saying Cannot cast Expression to bool.

The Fix: You have two choices:

The PyTorch Way (Dynamic): Let stock_level.value > 200 evaluate to a raw boolean. Re-trace the graph on every single tick. This is easier to code but slightly slower.

The JAX Way (Symbolic): Implement a drs.Where or drs.Switch operator that builds the condition into the AST.

Python
# Symbolic branching (Fastest, easy to visualize)
self.mill_rate = drs.Where(stock_level > 200, 6000, 3900)

personally i lean towards the jax approach though im not 100% sold. 

--- 

as i already do, DRSEngine must explicitly zero out the rate ASTs at the start of every tick before calling model.forward(). This is what i currently do and it works.

---

If level.rate equals an Expression(operator="+", left=A, right=B), calling a recursive Python .evaluate() method on an AST tree 10,000 times a second for Monte Carlo runs will be slow.

The Fix:
You don't need to over-engineer this on Day 1, but plan for an engine.compile() method. Once the simulation initializes, the engine can walk your ASTs and use Python's built-in compile() function or NumPy array operations to turn those nested object trees into a single, highly optimized bytecode function.

--- 

This feels clean and I like this, as I think we will do a pass on its own to "trace" and visualize so we can have a flag or mode for tracing

If you want to support this exact dynamic Python syntax (which is highly recommended for ease of use), you configure your Variable.__gt__ method to do both things depending on the engine's current state:

Python
class Variable:
    def __gt__(self, other):
        self._record_read_dependency() # <-- Graph is built here!
        
        # If we are in the middle of a simulation tick, return the actual boolean math!
        if ExecutionContext.is_running_simulation():
            other_val = other.value if isinstance(other, Variable) else other
            return self._value > other_val
            
        # Otherwise, if we are just tracing to build the visual graph, return the AST
        return Expression(">", self, other)
By doing this, your users get the absolute best of both worlds. They write standard, intuitive Python (if stock_level > 200), the engine evaluates it dynamically at runtime, and the framework still magically catches the read dependency to draw the visual edge!


--- 

Also this is a nice solution to the reading variables of other things for controller etc

You are absolutely correct, and this is a brilliant catch. If we force users to pass every dependency as an argument to forward(), we are destroying the object-oriented encapsulation that makes PyTorch so flexible.

In PyTorch, doing self.fc = nn.Linear(...) in __init__ and then just using self.fc(x) in forward without passing the weights as arguments is the standard pattern. If a user wants ModeController to hold a reference to self.stockpile and read it internally, the framework must support that seamlessly.

Fortunately, the ExecutionContext guardrail we designed to prevent bad mutations is the exact same tool we can use to automatically trace these implicit reads.

Here is how you solve this without forcing arguments, maintaining the perfect PyTorch feel:

The Solution: The "Read" Hook via Execution Context
We already established that ExecutionContext knows exactly which module is currently running its forward() pass.
Just as we used it to block illegal writes, we can use it to silently log reads.

If ModeController evaluates self.stockpile.level > 200, it has to access the level variable. We simply intercept that access.

The Implementation (variables.py)
Python
class Variable:
    def __init__(self, name: str, initial_value: float = 0.0):
        self.name = name
        self._value = initial_value
        self._owner = None # Set by Module.__setattr__

    def _record_read_dependency(self):
        """Silently tracks who is looking at this variable."""
        current_actor = ExecutionContext.get_current()
        
        # If a module is running, and it's looking at a variable it doesn't own...
        if current_actor is not None and current_actor is not self._owner:
            # We have discovered an implicit Information Edge!
            # The global graph can register: self._owner ---> current_actor
            current_actor.register_incoming_information_edge(self._owner)

    # 1. Intercepting exact value reads (e.g., for standard Python if-statements)
    @property
    def value(self):
        self._record_read_dependency()
        return self._value

    # 2. Intercepting AST Math Operations
    def __gt__(self, other):
        self._record_read_dependency()
        return Expression(operator=">", left=self, right=other)
        
    def __add__(self, other):
        self._record_read_dependency()
        return Expression(operator="+", left=self, right=other)
Why this is the Ultimate Approach
With this single addition, your framework achieves complete magic.

Look at how clean the user's code becomes. They don't have to define ports, they don't have to pass arguments, and they don't have to tell the visualizer what they are doing.

Python
class ModeController(drs.Module):
    def __init__(self, monitored_stockpile, target_mill):
        super().__init__()
        # User stores standard Python references
        self.stockpile = monitored_stockpile
        self.mill = target_mill

    def forward(self):
        # The ExecutionContext knows ModeController is running right now.
        
        # When Python evaluates this, stockpile.level.__gt__ is called.
        # The framework silently logs: Stockpile --> ModeController
        if self.stockpile.level > 200:
            
            # The framework silently logs: ModeController --> Mill
            self.mill.capacity_target = 6000
        else:
            self.mill.capacity_target = 3900

--- 

In future we can add a warning for order of execution not matching topoligical order leading to possible 1 tick delays