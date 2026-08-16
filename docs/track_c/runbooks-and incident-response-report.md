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


## 3. Walktrough of RB 001 reward miscalculation and how good it is
There is a big issue with the runbook and that is the runbook has a generic solution for cancellations in step 5.7 when there are two different cancellation paths and only one of them reverses points. The solution only applies to when no reverse of points happens even though one of the cancellation path reverses points. The cancellation path that doesn't reverse points does make mention that it doesn't. This would result in the unfamiliar engineer solving the problem for one customer without solving the actual path actually fixing the problem which is the endpoint. Even with this issue the runbook does solve help an unfamiliar engineer figure out the issues if they have enough confidence to trust the runbook. However a the fact that the AI generating the runbook not addressing the two different cancellation path seperately will cause some confusion with people who are not confident or notice the problem and get them side tracked.


## 4. Walktrough of RB 002 checkout fail under load and how good it is
So the second runbook would definitely cause the unfamiliar engineer to misdiagnose the problem of the incident and spend their first attempt to fix the problem with a solution that doesn't address the actual problem. The issue us that passes the timeout=0 key to other python files, so those file default to the timeout=5.0 hardcoded in to Python. The runbook repeatedly claims that busy_timeout is the main problem in in multiple steps of the runbook are thus false and result the unfamiliar engineer to not actually solve the problem until they realise it isn't the issue. The other steps of the runbook that don't say the busy_timeout is the issue will help the engineer fix the issue, but they need to realize the runbook's most recommended solution is false first, and that will take a while as they don't know the code well.


## 5. Verdict
The first runbook, RB 001, gets a pass as it's issue only result in one actual cause not being fixed and the rest of them solved, and the runbook does help indentify the problem via symptoms, and still deals with the issues the customer may experience in the incident scenario. It's just there may be some confusion caused by the lack of info on the 2 different cancellation paths.

The second runbook, RB002, does not get a pass as it's issue can easily result in an unfamiliar engineer misdianosing the problem based on the runbooks false recommendation on what the problem is repeated in the runbook. The runbook does have other steps that will allow an unfamiliar engineer to actually diaganose the issue, but that will only happen if they realize the main recommended solution is runbook is false. Some might never though as they may trust the runbook to much.


## 6. Note
I used Claude AI to do the walk through of the runbooks to double check them.

 

