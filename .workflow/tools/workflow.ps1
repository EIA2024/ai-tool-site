[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("doctor", "new-run", "status", "acquire", "release", "takeover", "checkpoint", "freeze", "queue")]
    [string]$Command = "status",

    [string]$Title,
    [string]$Slug,
    [ValidateSet("claude", "codex", "master", "human")]
    [string]$Agent,
    [string]$NextAction,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $output = & git @Args 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed:`n$output"
    }
    return ($output | Out-String).Trim()
}

function Get-RepoRoot {
    return (Invoke-Git rev-parse --show-toplevel)
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "Missing JSON file: $Path"
    }
    return (Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json)
}

function Write-JsonFile {
    param(
        [string]$Path,
        [object]$Value
    )
    $Value | ConvertTo-Json -Depth 20 | Set-Content -Encoding UTF8 $Path
}

function Get-Config {
    param([string]$Root)
    return Read-JsonFile (Join-Path $Root ".workflow/config.json")
}

function Get-Branch {
    return (Invoke-Git branch --show-current)
}

function Get-RunIdFromBranch {
    param(
        [string]$Branch,
        [object]$Config
    )
    $prefix = [string]$Config.workflow_branch_prefix
    if ($Branch.StartsWith($prefix)) {
        return $Branch.Substring($prefix.Length)
    }
    return $null
}

function Get-RunPaths {
    param(
        [string]$Root,
        [string]$RunId
    )
    $runDir = Join-Path $Root ".workflow/runs/$RunId"
    return @{
        RunDir = $runDir
        State = Join-Path $runDir "state.json"
        Checkpoint = Join-Path $runDir "checkpoint.json"
        Impact = Join-Path $runDir "impact.json"
    }
}

function Assert-RunOwnership {
    param(
        [string]$Root,
        [object]$Config
    )
    $branch = Get-Branch
    $runId = Get-RunIdFromBranch -Branch $branch -Config $Config
    if (-not $runId) {
        throw "Current branch '$branch' is not a workflow branch."
    }

    $paths = Get-RunPaths -Root $Root -RunId $runId
    $state = Read-JsonFile $paths.State

    if ([string]$state.run_id -ne $runId) {
        throw "Run ID mismatch: branch=$runId state=$($state.run_id)"
    }
    if ([string]$state.branch -ne $branch) {
        throw "Branch mismatch: current=$branch state=$($state.branch)"
    }

    return @{
        Branch = $branch
        RunId = $runId
        Paths = $paths
        State = $state
    }
}

function Get-LockPath {
    param([string]$Root)
    $runtime = Join-Path $Root ".workflow/runtime"
    New-Item -ItemType Directory -Force -Path $runtime | Out-Null
    return (Join-Path $runtime "agent-lock.json")
}

function Get-ChangedFiles {
    $lines = @(Invoke-Git status --short)
    if (-not $lines -or $lines.Count -eq 0 -or [string]::IsNullOrWhiteSpace(($lines -join ""))) {
        return @()
    }

    $result = @()
    foreach ($line in ($lines -split "`r?`n")) {
        if ($line.Length -ge 4) {
            $result += $line.Substring(3).Trim()
        }
    }
    return $result
}

function Copy-RunTemplate {
    param(
        [string]$Root,
        [string]$RunId,
        [string]$Title,
        [string]$Branch,
        [string]$WorktreePath,
        [string]$BaseBranch,
        [string]$BaseCommit
    )

    $template = Join-Path $Root ".workflow/templates/run"
    $target = Join-Path $Root ".workflow/runs/$RunId"
    if (Test-Path $target) {
        throw "Run directory already exists: $target"
    }
    Copy-Item -Recurse -Force $template $target

    $now = (Get-Date).ToString("o")

    $statePath = Join-Path $target "state.json"
    $state = Read-JsonFile $statePath
    $state.run_id = $RunId
    $state.title = $Title
    $state.branch = $Branch
    $state.worktree = $WorktreePath
    $state.base.branch = $BaseBranch
    $state.base.commit = $BaseCommit
    $state.updated_at = $now
    Write-JsonFile $statePath $state

    $checkpointPath = Join-Path $target "checkpoint.json"
    $checkpoint = Read-JsonFile $checkpointPath
    $checkpoint.run_id = $RunId
    $checkpoint.branch = $Branch
    $checkpoint.head_commit = $BaseCommit
    $checkpoint.created_at = $now
    Write-JsonFile $checkpointPath $checkpoint

    $impactPath = Join-Path $target "impact.json"
    $impact = Read-JsonFile $impactPath
    $impact.run_id = $RunId
    Write-JsonFile $impactPath $impact

    Get-ChildItem $target -Filter "*.md" | ForEach-Object {
        $text = Get-Content -Raw -Encoding UTF8 $_.FullName
        $text = $text -replace "(- Run ID:\s*)", "`$1$RunId"
        Set-Content -Encoding UTF8 $_.FullName $text
    }
}

$root = Get-RepoRoot
$config = Get-Config $root

switch ($Command) {
    "doctor" {
        $required = @(
            "AGENTS.md",
            "CLAUDE.md",
            ".workflow/config.json",
            ".workflow/core/PROTOCOL.md",
            ".workflow/core/RUN-PROTOCOL.md",
            ".workflow/core/TAKEOVER-PROTOCOL.md",
            ".workflow/core/INTEGRATION-PROTOCOL.md",
            ".workflow/control/REGISTRY.json",
            ".workflow/control/MERGE_QUEUE.json"
        )

        $missing = @()
        foreach ($item in $required) {
            if (-not (Test-Path (Join-Path $root $item))) {
                $missing += $item
            }
        }
        if ($missing.Count -gt 0) {
            throw "Missing required files:`n$($missing -join "`n")"
        }

        Get-ChildItem (Join-Path $root ".workflow") -Recurse -Filter "*.json" | ForEach-Object {
            Get-Content -Raw -Encoding UTF8 $_.FullName | ConvertFrom-Json | Out-Null
        }

        $branch = Get-Branch
        $head = Invoke-Git rev-parse HEAD
        Write-Host "Doctor: PASS"
        Write-Host "Repository: $root"
        Write-Host "Branch: $branch"
        Write-Host "HEAD: $head"
        Write-Host "JSON files: valid"
    }

    "new-run" {
        if ([string]::IsNullOrWhiteSpace($Title) -or [string]::IsNullOrWhiteSpace($Slug)) {
            throw "new-run requires -Title and -Slug."
        }

        $baseBranch = [string]$config.base_branch
        $currentBranch = Get-Branch
        if ($currentBranch -ne $baseBranch) {
            throw "Create Runs from '$baseBranch'. Current branch is '$currentBranch'."
        }

        $status = Invoke-Git status --porcelain
        if (-not [string]::IsNullOrWhiteSpace($status)) {
            throw "The base Worktree must be clean before new-run."
        }

        $slugSafe = ($Slug.ToLowerInvariant() -replace "[^a-z0-9-]", "-" -replace "-+", "-").Trim("-")
        if ([string]::IsNullOrWhiteSpace($slugSafe)) {
            throw "Slug does not contain usable characters."
        }

        $registryPath = Join-Path $root ".workflow/control/REGISTRY.json"
        $registry = Read-JsonFile $registryPath
        $datePart = (Get-Date).ToString("yyyyMMdd")
        $sameDay = @($registry.runs | Where-Object { [string]$_.run_id -like "WF-$datePart-*" })
        $sequence = $sameDay.Count + 1
        do {
            $runId = "WF-$datePart-{0:D3}-$slugSafe" -f $sequence
            $exists = @($registry.runs | Where-Object { [string]$_.run_id -eq $runId }).Count -gt 0
            $sequence++
        } while ($exists)

        $branch = "$($config.workflow_branch_prefix)$runId"
        $baseCommit = Invoke-Git rev-parse HEAD

        $worktreeRoot = [System.IO.Path]::GetFullPath((Join-Path $root ([string]$config.worktree_root)))
        New-Item -ItemType Directory -Force -Path $worktreeRoot | Out-Null
        $worktreePath = Join-Path $worktreeRoot $runId

        Copy-RunTemplate `
            -Root $root `
            -RunId $runId `
            -Title $Title `
            -Branch $branch `
            -WorktreePath $worktreePath `
            -BaseBranch $baseBranch `
            -BaseCommit $baseCommit

        $entry = [ordered]@{
            run_id = $runId
            title = $Title
            branch = $branch
            worktree = $worktreePath
            base_branch = $baseBranch
            base_commit = $baseCommit
            lifecycle_status = "registered"
            candidate_sha = $null
            dependencies = @()
            created_at = (Get-Date).ToString("o")
            updated_at = (Get-Date).ToString("o")
        }

        $registry.runs = @($registry.runs) + @($entry)
        Write-JsonFile $registryPath $registry

        Invoke-Git add ".workflow/control/REGISTRY.json" ".workflow/runs/$runId" | Out-Null
        Invoke-Git commit -m "chore(workflow): register $runId" | Out-Null
        $registrationCommit = Invoke-Git rev-parse HEAD

        Invoke-Git worktree add -b $branch $worktreePath $registrationCommit | Out-Null

        Write-Host "Run created."
        Write-Host "Run ID: $runId"
        Write-Host "Branch: $branch"
        Write-Host "Worktree: $worktreePath"
        Write-Host "Open this folder in Claude Code Desktop or Codex."
    }

    "status" {
        $branch = Get-Branch
        $runId = Get-RunIdFromBranch -Branch $branch -Config $config
        Write-Host "Repository: $root"
        Write-Host "Branch: $branch"
        Write-Host "HEAD: $(Invoke-Git rev-parse HEAD)"
        Write-Host "Dirty: $(-not [string]::IsNullOrWhiteSpace((Invoke-Git status --porcelain)))"

        if ($runId) {
            $context = Assert-RunOwnership -Root $root -Config $config
            $state = $context.State
            Write-Host "Run ID: $runId"
            Write-Host "Lifecycle: $($state.lifecycle_status)"
            Write-Host "State: $($state.current_state)"
            Write-Host "State status: $($state.state_status)"
            Write-Host "Current agent: $($state.agent.current_agent)"
            Write-Host "Next action: $($state.next_action)"
            Write-Host "Candidate: $($state.candidate.status) $($state.candidate.sha)"
        } else {
            Write-Host "Mode: project/master"
        }

        $lockPath = Get-LockPath $root
        if (Test-Path $lockPath) {
            $lock = Read-JsonFile $lockPath
            Write-Host "Lock: $($lock.active_agent) since $($lock.acquired_at)"
        } else {
            Write-Host "Lock: free"
        }
    }

    "acquire" {
        if (-not $Agent) {
            throw "acquire requires -Agent."
        }

        $context = Assert-RunOwnership -Root $root -Config $config
        $lockPath = Get-LockPath $root
        if (Test-Path $lockPath) {
            $lock = Read-JsonFile $lockPath
            if ([string]$lock.active_agent -ne $Agent) {
                throw "Worktree is locked by '$($lock.active_agent)'."
            }
            Write-Host "Lock already owned by $Agent."
            break
        }

        $lock = [ordered]@{
            schema_version = 1
            run_id = $context.RunId
            active_agent = $Agent
            acquired_at = (Get-Date).ToString("o")
            checkpoint_id = $context.State.agent.last_checkpoint_id
        }
        Write-JsonFile $lockPath $lock

        $state = $context.State
        $state.agent.last_agent = $state.agent.current_agent
        $state.agent.current_agent = $Agent
        $state.updated_at = (Get-Date).ToString("o")
        Write-JsonFile $context.Paths.State $state

        Write-Host "Lock acquired by $Agent."
    }

    "release" {
        if (-not $Agent) {
            throw "release requires -Agent."
        }

        $context = Assert-RunOwnership -Root $root -Config $config
        $lockPath = Get-LockPath $root
        if (-not (Test-Path $lockPath)) {
            Write-Host "Lock is already free."
            break
        }

        $lock = Read-JsonFile $lockPath
        if ([string]$lock.active_agent -ne $Agent -and -not $Force) {
            throw "Lock belongs to '$($lock.active_agent)'. Use -Force only with human authorization."
        }

        Remove-Item -Force $lockPath
        $state = $context.State
        $state.agent.last_agent = $state.agent.current_agent
        $state.agent.current_agent = $null
        $state.updated_at = (Get-Date).ToString("o")
        Write-JsonFile $context.Paths.State $state
        Write-Host "Lock released."
    }

    "takeover" {
        if (-not $Agent) {
            throw "takeover requires -Agent."
        }

        $context = Assert-RunOwnership -Root $root -Config $config
        $lockPath = Get-LockPath $root

        if (Test-Path $lockPath) {
            $lock = Read-JsonFile $lockPath
            if (-not $Force) {
                throw "Lock is owned by '$($lock.active_agent)'. Obtain release or use -Force with explicit authorization."
            }
            Remove-Item -Force $lockPath
        }

        $newLock = [ordered]@{
            schema_version = 1
            run_id = $context.RunId
            active_agent = $Agent
            acquired_at = (Get-Date).ToString("o")
            checkpoint_id = $context.State.agent.last_checkpoint_id
            forced = [bool]$Force
        }
        Write-JsonFile $lockPath $newLock

        $state = $context.State
        $state.agent.last_agent = $state.agent.current_agent
        $state.agent.current_agent = $Agent
        $state.updated_at = (Get-Date).ToString("o")
        Write-JsonFile $context.Paths.State $state
        Write-Host "Takeover completed by $Agent. Inspect checkpoint and Git Diff before writing."
    }

    "checkpoint" {
        if (-not $Agent -or [string]::IsNullOrWhiteSpace($NextAction)) {
            throw "checkpoint requires -Agent and -NextAction."
        }

        $context = Assert-RunOwnership -Root $root -Config $config
        $lockPath = Get-LockPath $root
        if (-not (Test-Path $lockPath)) {
            throw "Acquire the agent lock before creating a checkpoint."
        }
        $lock = Read-JsonFile $lockPath
        if ([string]$lock.active_agent -ne $Agent) {
            throw "Lock belongs to '$($lock.active_agent)'."
        }

        $checkpoint = Read-JsonFile $context.Paths.Checkpoint
        $oldId = [string]$checkpoint.checkpoint_id
        $number = 0
        if ($oldId -match "^CP-(\d+)$") {
            $number = [int]$Matches[1]
        }
        $checkpoint.checkpoint_id = "CP-{0:D3}" -f ($number + 1)
        $checkpoint.run_id = $context.RunId
        $checkpoint.branch = $context.Branch
        $checkpoint.head_commit = Invoke-Git rev-parse HEAD
        $checkpoint.working_tree_dirty = -not [string]::IsNullOrWhiteSpace((Invoke-Git status --porcelain))
        $checkpoint.workflow_state = $context.State.current_state
        $checkpoint.state_status = $context.State.state_status
        $checkpoint.current_step = $context.State.current_step
        $checkpoint.created_at = (Get-Date).ToString("o")
        $checkpoint.created_by = $Agent
        $checkpoint.handoff_to = "any"
        $checkpoint.changed_files = @(Get-ChangedFiles)
        $checkpoint.next_action = $NextAction
        Write-JsonFile $context.Paths.Checkpoint $checkpoint

        $state = $context.State
        $state.agent.last_checkpoint_id = $checkpoint.checkpoint_id
        $state.next_action = $NextAction
        $state.updated_at = (Get-Date).ToString("o")
        Write-JsonFile $context.Paths.State $state

        Write-Host "Checkpoint $($checkpoint.checkpoint_id) written."
    }

    "freeze" {
        if (-not $Agent) {
            throw "freeze requires -Agent."
        }

        $context = Assert-RunOwnership -Root $root -Config $config
        $status = Invoke-Git status --porcelain
        if (-not [string]::IsNullOrWhiteSpace($status)) {
            throw "Candidate freeze requires a clean working tree."
        }

        $sha = Invoke-Git rev-parse HEAD
        $state = $context.State
        if ([string]$state.current_state -ne "S8_CANDIDATE") {
            throw "Candidate can freeze only in S8_CANDIDATE."
        }

        $state.candidate.status = "frozen"
        $state.candidate.sha = $sha
        $state.candidate.frozen_at = (Get-Date).ToString("o")
        $state.candidate.validation_sha = $sha
        $state.candidate.review_sha = $sha
        $state.lifecycle_status = "candidate_frozen"
        $state.state_status = "awaiting_approval"
        $state.next_action = "Request APPROVE CANDIDATE $($context.RunId) $sha"
        $state.updated_at = (Get-Date).ToString("o")
        Write-JsonFile $context.Paths.State $state

        Write-Host "Candidate frozen at $sha."
        Write-Host "Required token: APPROVE CANDIDATE $($context.RunId) $sha"
    }

    "queue" {
        $context = Assert-RunOwnership -Root $root -Config $config
        $state = $context.State
        $sha = [string]$state.candidate.sha

        if ([string]::IsNullOrWhiteSpace($sha) -or [string]$state.candidate.status -ne "frozen") {
            throw "No frozen candidate."
        }
        if ([string]$state.approvals.candidate -ne $sha) {
            throw "Candidate approval does not match SHA $sha."
        }

        $queuePath = Join-Path $root ".workflow/control/MERGE_QUEUE.json"
        $queue = Read-JsonFile $queuePath
        $exists = @($queue.items | Where-Object { [string]$_.run_id -eq $context.RunId -and [string]$_.candidate_sha -eq $sha }).Count -gt 0
        if (-not $exists) {
            $item = [ordered]@{
                run_id = $context.RunId
                source_branch = $context.Branch
                candidate_sha = $sha
                dependencies = @($state.dependencies)
                status = "queued"
                queued_at = (Get-Date).ToString("o")
            }
            $queue.items = @($queue.items) + @($item)
            Write-JsonFile $queuePath $queue
        }

        $state.lifecycle_status = "merge_queued"
        $state.state_status = "completed"
        $state.next_action = "Wait for Master Integration."
        $state.updated_at = (Get-Date).ToString("o")
        Write-JsonFile $context.Paths.State $state

        Write-Host "Candidate queued. Commit control/state changes before leaving the Run."
    }
}
