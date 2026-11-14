# Problem

Open weight agents don’t have the same guards that harnesses like Claude Code imposes, leaving them more vulnerable to attack. Still, open weights are a deliberate design choice used by individuals and enterprises, for privacy, self-hosting, cost and fine-tuning. 

# Solution

An autonomous agent which acts a protect layer for open-source agents. It stops the agent before it makes an action which leaves the local device to guard against anything malicious, for example prompt injection.

# Core points 
- The human can't be trusted to read a recommendation or check a tool call. Relates back to the Anthropic research that humans don't actaully check

# Demo Plan
1. Local agent call on a control task results in successful attack
2. Local agent call on a control task results in an unsucessful attack
3. Break down of what our guard is doing

# System Flow

## Installer

1. One line CLI
2. Scans the user's device to decide what local agents it should be applicable to
3. Configures the setting so that tool calls are sent to the guard, rather than directly to the tool

## Guard Process

1. Developer gives the local agent a task
2. Agent proposes a tool call (read file, run shell, http reuqest)
3. The call goes to the guard - not to the tool
4. The request is compared with the institutional policy
    - If already permissioned, returns approval
    - If issues, returns no with reason for local agent to reconsider
    - If no issues, goes to adaptive policy
5. The request is compared with the guard's adaptive policy
    - If already permissioned, returns approval with a flag
    - If issues, return no with reason for local agent to reconsider
    - If no issues, goes on to agent
6. Agent decides, with a fine tuned model as the brain. If it reached this stage, it should be "not obvious". "Obvious" should get defined over time as the guard policy iteratively updates. It must reason over several steps. Any server's domain is researched over Tavily (domain only, not payload). It's also tasked with keep the adaptive policy up to date. 
    - If no issues, returns approval with a flag
    - If issues, checks whether 



---

# Notes

## Issues
1. The policy gets updated is risky. Can it really be trusted with its policy? 

## Points
1. Only the hostname can be sent - never the payload. Treat the search result as untrusted that the model could be injected by.

## Open Questions
1. After the guard returns 'yes', what stops the next (verified) tool call 

## Autonomous claim
From Claude: "If you want to claim "autonomous agent" for the whole product, the strongest honest version is that the system lets the coding agent run unattended, with the guard making the decisions a human would otherwise make."