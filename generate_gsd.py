import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content.strip())

base_dir = '/root/aziza-build'

# Phase 1: GSD Directories and Templates
gsd_dirs = ['epics', 'milestones', 'stories', 'tasks', 'reviews', 'completed', 'templates', 'metrics', 'checklists', 'workflows']
for d in gsd_dirs:
    os.makedirs(os.path.join(base_dir, '.gsd', d), exist_ok=True)

write_file(f'{base_dir}/.gsd/epics/VOICE_PLATFORM.md', '# Epic: Voice Platform\n\nGoal: Low latency voice interactions.')
write_file(f'{base_dir}/.gsd/epics/PERSONAPLEX.md', '# Epic: PersonaPlex\n\nGoal: Dynamic emotion injection.')
write_file(f'{base_dir}/.gsd/epics/MULTILINGUAL.md', '# Epic: Multilingual Support\n\nGoal: Seamless English, Russian, Uzbek translation.')
write_file(f'{base_dir}/.gsd/epics/DEPLOYMENT.md', '# Epic: Deployment\n\nGoal: Automated CI/CD.')
write_file(f'{base_dir}/.gsd/epics/TRAINING.md', '# Epic: Training\n\nGoal: Fine-tune LoRA adapters.')

write_file(f'{base_dir}/.gsd/stories/VOICE-001.md', '# Story: VOICE-001\n\nReduce first token latency.')
write_file(f'{base_dir}/.gsd/stories/VOICE-002.md', '# Story: VOICE-002\n\nImprove voice activity detection.')

write_file(f'{base_dir}/.gsd/tasks/TASK-0001.md', '# Task: TASK-0001\n\nImplement streaming chunks.')
write_file(f'{base_dir}/.gsd/tasks/TASK-0002.md', '# Task: TASK-0002\n\nProfile audio bridge.')

write_file(f'{base_dir}/.gsd/checklists/DEFAULT_TASK.md', '# Default Task Checklist\n\n- [ ] Implemented\n- [ ] Tested')
write_file(f'{base_dir}/.gsd/checklists/CODE_REVIEW.md', '# Code Review Checklist\n\n- [ ] No duplicate code\n- [ ] Performance OK')
write_file(f'{base_dir}/.gsd/checklists/DEPLOYMENT.md', '# Deployment Checklist\n\n- [ ] PM2 updated\n- [ ] Configs verified')
write_file(f'{base_dir}/.gsd/checklists/QA.md', '# QA Checklist\n\n- [ ] End-to-end tests pass')

write_file(f'{base_dir}/.gsd/metrics/engineering_metrics.md', '# Engineering Metrics\n\n- Build Success Rate\n- Test Pass Rate\n- Documentation Coverage')

write_file(f'{base_dir}/.gsd/workflows/development_loop.md', '''# Development Loop
User Goal -> Planner -> Find Epic -> Find Story -> Find Task -> Load Engineering Context -> Load Agent -> Execute Task -> Run Tests -> Review -> Update Documentation -> Commit -> Close Task
No other workflow is allowed.
''')

write_file(f'{base_dir}/.gsd/workflows/review_loop.md', '# Review Loop\n\nReview code against guidelines.')
write_file(f'{base_dir}/.gsd/workflows/release_process.md', '# Release Process\n\nMerge to main, deploy to production.')

# Phase 2
write_file(f'{base_dir}/engineering/DEVELOPMENT_WORKFLOW.md', '''# Development Workflow
The ONLY allowed workflow:
User Goal -> Planner -> Find Epic -> Find Story -> Find Task -> Load Engineering Context -> Load Agent -> Execute Task -> Run Tests -> Review -> Update Documentation -> Commit -> Close Task
No other workflow is allowed.
''')

# Phase 3
write_file(f'{base_dir}/engineering/ARCHITECTURE_FREEZE.md', '''# Architecture Freeze Policy
The following changes require explicit human approval:
- New frameworks
- New databases
- New AI models
- Major directory restructuring
- Authentication redesign
- Deployment redesign
- Infrastructure replacement
- Messaging architecture changes
- Model provider replacement
- Vector database replacement
Everything else may proceed automatically.
OpenCode must check this policy before implementing any task.
''')

# Phase 4
write_file(f'{base_dir}/engineering/DEVELOPMENT_CHARTER.md', '''# Development Charter
Mandatory rules:
- One task at a time.
- One branch per task.
- Never invent work.
- Never skip planning.
- Never speculate.
- Never duplicate functionality.
- Always search before implementing.
- Always read engineering documentation first.
- Always update engineering documentation.
- Always execute tests.
- Never ignore failing tests.
- Never modify architecture without approval.
- Never change public APIs without approval.
- Never rewrite completed work.
- Every completed task requires a summary.
- Every task must reference an Epic and Story.
- Every task must include acceptance criteria.
''')

# Phase 5
write_file(f'{base_dir}/.gsd/checklists/task_completion.md', '''# Task Completion Gates
Every task must satisfy:

Implementation
[ ] Code complete
[ ] Acceptance criteria met

Quality
[ ] Unit tests pass
[ ] Integration tests pass
[ ] Smoke tests pass
[ ] Performance acceptable
[ ] Lint passes

Documentation
[ ] Documentation updated
[ ] ADR updated if required
[ ] Changelog updated
[ ] Session log updated

Review
[ ] QA reviewed
[ ] Reviewer approved

Git
[ ] Commit created
[ ] Branch synchronized
[ ] Ready to merge

Tasks may not transition to Completed until every applicable gate passes.
''')

# Phase 6
write_file(f'{base_dir}/engineering/history/2026-07-10-session-001.md', '# Session 1\nGoal: Cleanup')
write_file(f'{base_dir}/engineering/history/2026-07-10-session-002.md', '# Session 2\nGoal: Refactoring')
write_file(f'{base_dir}/engineering/history/2026-07-11-session-001.md', '# Session 3\nGoal: GSD Governance')

# Phase 7
write_file(f'{base_dir}/.opencode/agents/repository_guardian.md', '''# Agent: Repository Guardian
**Purpose**: Prevent technical debt.
Before every implementation it performs:
- Repository search
- Duplicate detection
- Architecture validation
- ADR lookup
- Policy validation
- Dependency validation
- Directory validation
- Naming validation

If any violation is detected (Existing implementation, Duplicate functionality, Architecture violation, Policy violation, Conflicting design, Missing ADR, Broken dependency), the Guardian blocks execution until reviewed.
''')

# Phase 8
write_file(f'{base_dir}/.gsd/templates/Epic.md', '# Epic Template\n\n## Goal\n## Stories\n')
write_file(f'{base_dir}/.gsd/templates/Story.md', '# Story Template\n\n## Goal\n## Tasks\n')
write_file(f'{base_dir}/.gsd/templates/Task.md', '# Task Template\n\n## Goal\n## Acceptance Criteria\n## Assigned Agent\n## Completion Checklist\n')

# Phase 9 (Metrics already partially created above)

# Phase 10
agents = ['Planner', 'Architect', 'Backend', 'Frontend', 'Training', 'Inference', 'Voice', 'PersonaPlex', 'DevOps', 'QA', 'Reviewer', 'Documentation', 'Repository Guardian']
for agent in agents:
    content = f'''# Agent: {agent}
## Purpose
Define purpose here.
## Responsibilities
Define responsibilities here.
## Allowed Directories
Define allowed directories here.
## Forbidden Actions
Define forbidden actions here.
## Required Documentation
Define required documentation here.
## Completion Criteria
Define completion criteria here.
## Required Tests
Define required tests here.
## Escalation Conditions
Define escalation conditions here.
'''
    write_file(f'{base_dir}/.opencode/agents/{agent.lower().replace(" ", "_")}.md', content)

# Phase 12
engineering_files = ['GOVERNANCE.md', 'ENGINEERING_RULES.md', 'QUALITY_GATES.md', 'PROJECT_STATUS.md', 'PROJECT_HEALTH.md', 'TECHNICAL_DEBT.md', 'AI_WORKFLOW.md', 'AGENT_RESPONSIBILITIES.md', 'GSD_GUIDE.md', 'OPENCODE_GUIDE.md']
for file in engineering_files:
    write_file(f'{base_dir}/engineering/{file}', f'# {file.split(".")[0]}\n\nContent for {file}.')

print("GSD Governance System implemented successfully.")
