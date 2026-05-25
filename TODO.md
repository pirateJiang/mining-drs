
Strong recommendation: separate “model” from “policy”

Currently your mine logic mixes:

physics
operations
control strategy

Example:

if ore2_stock.value > critical:

This is operational policy, not physical state evolution.

You should separate:

Plant model
ore flows
stockpiles
extraction
Control policy
campaign switching
contingency activation
shutdown logic

Like:

MinePlant
MineController
DRSEngine

This is exactly how:

control systems
RL environments
robotics stacks
industrial simulators

are usually structured.

Very important for scaling


One very important missing feature: composability

Right now everything is one giant model.

You eventually want:

Mine()
    .add(Crusher())
    .add(HaulFleet())
    .add(Stockpile())

with message passing or shared flows.

Without composability, industrial systems become unmanageable.


---
UNSURE ABOUT EVENTS BUT IF I DID SOMETHING LIKE THIS: 
Your biggest missing abstraction: Events

Right now thresholds are overloaded:

physical constraints
transitions
event triggers
guards

These should be separate concepts.

You currently do:

ore_stock.lower_threshold = target

But this mixes:

constraint
event condition
control logic

You likely need:

Event(
    name="ore_stock_low",
    condition=lambda: ore_stock.value < target
)

Then transitions subscribe to events.

This becomes extremely important once you add:

multiple simultaneous triggers
priorities
stochastic failures
maintenance systems
queues
dispatch logic

Without events, the engine eventually becomes a giant threshold evaluator

Something similar to events but for transitions: 
This:

self.registry.register_transition(
    MineMode.MODE_A,
    MineMode.MODE_A_MINE_SURGING,
    self.ore1_stock,
    is_upper=False,
)

is readable initially, but becomes impossible to reason about at scale.

You need a real transition abstraction.

Instead of positional semantics:

register_transition(mode, action, signal, is_upper=False)

use something like:

Transition(
    source=MineMode.MODE_A,
    target=MineMode.MODE_A_MINE_SURGING,
    trigger=self.ore1_stock < 0,
)

or:

@transition(
    source=MODE_A,
    when=ore1_stock.lower_crossing
)
def enter_surging():
    return MODE_A_MINE_SURGING

Your current API hides semantics in:

booleans
argument order
implicit conventions

This becomes dangerous in large systems.