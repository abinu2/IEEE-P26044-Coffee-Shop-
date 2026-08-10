| Field | Value |
|-------|-------|
| Project | Coffee Shop Project |
| Track | C - Runbooks and Incident response report|
| Date | 2026-08-08 |
| App runbooks are made for | FastAPI coffee shop app |
| AI used to generate runbooks | Claude |

## 1. What are the incident-response runbooks for
In this Project runbooks are for checking if the code base behaves to possible realistic failures that can happen to a coffee shop in real life.


## 2. The chosen incident scenarios
I was given 3 possible incident scenarios to choose 2 from to test. The 2 incident scenarios I choose to test are reward miscalculation, and checkout fail under load.


## 3. Walktrough of reward miscalculation runbook and how good it is
This runbook was for the incident scenario for when a reward miscalualtion happened. The root causes are easily reachable from the steps on the run book. From the first step that recommends you pull the ledger to check the info to the list of the causes of the incident in order of how easily they can happen, you can quickly get to to the cause of the problem. There is also a diagnostic tree for reference. 
Two issues with runbook for anyone unfamiliar the code that make it a little difficult to resolve the problem. The first issue is with the part 6.6 for the possible cause of duplicate reward earn happened, bypassing a check for the issue for the balance and reward ledger not being the same. But because the balanace and reward ledger are already set to be the same value with ease, this check can't fail due to how the code is written. So the runbook is covering a possible cause that can't even happen.
The second issue which is worse through out the runbook steps, it suggests you consult the logs of the codebase, even though the codebase doesn't do any logging, or recompute the expected values using the code functions without mentioning how to call the functions, what functions to call, or where the output goes. It is hard to check logs when they don't exist and how retest the expected values when you don't know how to call the right functions and where the output ends up in the code.



## 4. Walktrough of checkout fail under load runbook and how good it is
This runbook was for the incident scenario for when a checkout fails due to load issues. Same as this one the logbook has a nice set of steps and a diagnostic tree to help you find the source of the problem. However, it only indentifies the root cause for only some scenarios, while others, like the step for the evalutaing the 502s, only help figure out what is not the cause and tells you where you can go to figure out what the cause is yourself.
The problem with that along with the rest of this runbook is that it relies on you to do a check of the codes logs alot. The problem is, as mentioned with the other runbook, the code does no logging at all. And the runbook relies on you to do this alot to get to identify the actual root cause. It is not good for the runbook to to heavily require the user to check something that doesn't exist to solve a problem.


## 5. Verdict
As a result of above analyses of the runbooks, I can conclude that a DevOps engineer unfamiliar with this codebase will have trouble and has a good chance of not being able to solve the problem. Not only does one of the runbooks suggest check for issue that can't happen, but they also do explain where any output goes or how to call the correct functions when it asks you the recompute values via functions. 
Also both suggests for a number of steps to check the logs of the code which are non existant. That last one is mostly likely because Claude AI falsely assumes all codebases have logs of some sort. Plus one of the runbooks will in some cases only rule out what is not the issue and not identify what the issue actually is. So yeah, these are not bad, but they are not helping someone unfamiliar with the code identify the correct problem.


## 6. To be possiblly done 

If the part of the code that hasn't been done yet is completed and track b is done again, then a new set of runbooks will be done.
 

