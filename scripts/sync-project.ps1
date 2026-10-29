[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
 [string]$RepoPath = (Split-Path -Parent $PSScriptRoot),
 [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$Remote = 'origin',
 [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._/-]*$')][string]$Branch = 'main',
 [switch]$FetchOnly,
 [string]$LogPath = (Join-Path $env:LOCALAPPDATA 'Echo\logs\sync-project.log')
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$script:GitExitCode = 0
$script:SyncExitCode = 0
$script:GitOutput = @()
$lockStream = $null
function Write-SyncLog {
 param([string]$Outcome,[string]$Message)
 $line = '{0} outcome={1} branch={2} message={3}' -f [DateTimeOffset]::Now.ToString('o'),$Outcome,$Branch,$Message
 try {$parent=Split-Path -Parent $LogPath; if($parent){New-Item -ItemType Directory -Path $parent -Force|Out-Null}; Add-Content -LiteralPath $LogPath -Value $line -Encoding utf8}
 catch {Write-Warning 'Could not write the sync log.'}
}
function Invoke-GitQuiet {
 param([string[]]$Arguments)
 $script:GitOutput=@(& git -C $script:ResolvedRepo @Arguments 2>$null)
 $script:GitExitCode=$LASTEXITCODE
 return $script:GitOutput
}
function Stop-Sync {
 param([string]$Outcome,[string]$Message,[int]$Code=0)
 Write-SyncLog -Outcome $Outcome -Message $Message
 if($Outcome -eq 'error'){Write-Error $Message -ErrorAction Continue}
 elseif($Outcome -eq 'manual'){Write-Warning $Message}
 else{Write-Host $Message}
 if($Outcome -eq 'manual' -and $Code -eq 0){$Code=2}
 if($Code -ne 0){$failure=[InvalidOperationException]::new($Message); $failure.Data['EchoSyncExitCode']=$Code; throw $failure}
}
try {
 if(-not(Test-Path -LiteralPath $RepoPath -PathType Container)){throw 'Repository folder does not exist.'}
 $script:ResolvedRepo=(Resolve-Path -LiteralPath $RepoPath).Path
 $root=Invoke-GitQuiet @('rev-parse','--show-toplevel')|Select-Object -First 1
 if($script:GitExitCode -ne 0 -or -not $root){throw 'The selected folder is not a Git working tree.'}
 if((Resolve-Path -LiteralPath $root).Path -ne $script:ResolvedRepo){throw 'Pass the exact repository root path.'}
 $commonText=Invoke-GitQuiet @('rev-parse','--git-common-dir')|Select-Object -First 1
 if($script:GitExitCode -ne 0 -or -not $commonText){throw 'Could not locate Git metadata.'}
 if([IO.Path]::IsPathRooted($commonText)){$commonDir=$commonText}else{$commonDir=Join-Path $script:ResolvedRepo $commonText}
 $commonDir=(Resolve-Path -LiteralPath $commonDir).Path
 try {$lockStream=[IO.File]::Open((Join-Path $commonDir 'echo-sync.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
 catch {Stop-Sync -Outcome manual -Message 'Another Echo sync is running. Retry when it finishes.' -Code 2; return}
 foreach($name in @('index.lock','HEAD.lock')){if(Test-Path -LiteralPath (Join-Path $commonDir $name)){Stop-Sync -Outcome manual -Message 'Git reports another operation in progress. Retry when it finishes.' -Code 2; return}}
 $null=Invoke-GitQuiet @('show-ref','--verify','--quiet',"refs/heads/$Branch")
 if($script:GitExitCode -ne 0){Stop-Sync -Outcome manual -Message "Local $Branch does not exist. No branch was created or switched." -Code 2; return}
 $url=Invoke-GitQuiet @('remote','get-url',$Remote)
 if($script:GitExitCode -ne 0 -or -not $url){Stop-Sync -Outcome error -Message 'Configured remote is unavailable. Check its name and sign-in.' -Code 1; return}
 # Suppress Git output because a misconfigured URL could contain credentials.
 $null=Invoke-GitQuiet @('fetch','--no-tags','--no-recurse-submodules',$Remote,$Branch)
 if($script:GitExitCode -ne 0){Stop-Sync -Outcome error -Message 'Fetch failed. Check network and Git Credential Manager sign-in. Details are omitted from the log.' -Code 1; return}
 Write-Host "Fetched $Remote/$Branch."
 if($FetchOnly){Stop-Sync -Outcome fetched-only -Message 'Fetch-only mode: local branches and files were not changed.'; return}
 $localRef="refs/heads/$Branch"; $remoteRef="refs/remotes/$Remote/$Branch"
 $localSha=Invoke-GitQuiet @('rev-parse','--verify',$localRef)|Select-Object -First 1
 if($script:GitExitCode -ne 0){Stop-Sync -Outcome manual -Message 'Could not read local target branch. No branch was changed.' -Code 2; return}
 $remoteSha=Invoke-GitQuiet @('rev-parse','--verify',$remoteRef)|Select-Object -First 1
 if($script:GitExitCode -ne 0){Stop-Sync -Outcome manual -Message 'Expected remote-tracking branch is missing. Check remote configuration.' -Code 2; return}
 if($localSha -eq $remoteSha){Stop-Sync -Outcome up-to-date -Message "Local $Branch already matches the fetched remote."; return}
 $null=Invoke-GitQuiet @('merge-base','--is-ancestor',$localSha,$remoteSha)
 if($script:GitExitCode -ne 0){Stop-Sync -Outcome manual -Message "Local $Branch cannot be fast-forwarded. No local branch changed; inspect history manually." -Code 2; return}
 $current=Invoke-GitQuiet @('branch','--show-current')|Select-Object -First 1
 $worktrees=Invoke-GitQuiet @('worktree','list','--porcelain')
 if($script:GitExitCode -ne 0){Stop-Sync -Outcome manual -Message 'Could not inspect worktrees. No local branch changed.' -Code 2; return}
 $mainPath=$null; $candidate=$null
 foreach($line in $worktrees){if($line -match '^worktree (.+)$'){$candidate=$matches[1]}elseif($line -eq "branch $localRef"){$mainPath=$candidate}}
 if($mainPath -and ((Resolve-Path -LiteralPath $mainPath).Path -ne $script:ResolvedRepo)){Stop-Sync -Outcome manual -Message "Local $Branch is checked out in another worktree. That worktree was left untouched."; return}
 if($mainPath){
  if($current -ne $Branch){Stop-Sync -Outcome manual -Message "Unexpected $Branch worktree state. No branch switched or updated."; return}
  $dirty=Invoke-GitQuiet @('status','--porcelain','--untracked-files=normal')
  if($script:GitExitCode -ne 0 -or $dirty.Count -gt 0){Stop-Sync -Outcome manual -Message "Local $Branch has uncommitted changes. Files were left untouched."; return}
  $editors=@(Get-Process -Name @('Code','Code - Insiders','studio64','devenv','idea64','rider64') -ErrorAction SilentlyContinue)
  if($editors.Count -gt 0){Stop-Sync -Outcome manual -Message 'A common code editor is running. Close it and rerun to avoid refreshing open files.'; return}
  try {$builds=@(Get-CimInstance Win32_Process -ErrorAction Stop|Where-Object{$_.Name -match '^(java|javaw|gradle|dotnet|msbuild)\.exe$' -and $_.CommandLine -match '(?i)(gradle|gradlew|MSBuild|dotnet\s+build|KotlinCompile)'})}
  catch {Stop-Sync -Outcome manual -Message 'Could not check active builds. Rerun after confirming no build is running.'; return}
  if($builds.Count -gt 0){Stop-Sync -Outcome manual -Message 'A build appears to be running. Files were left untouched.'; return}
  if($PSCmdlet.ShouldProcess("local $Branch",'Fast-forward to fetched remote')){
   $null=Invoke-GitQuiet @('merge','--ff-only',$remoteRef)
   if($script:GitExitCode -ne 0){Stop-Sync -Outcome manual -Message "Git could not fast-forward $Branch. No conflict was resolved automatically."; return}
   Stop-Sync -Outcome updated -Message "Local $Branch fast-forwarded. Other branches were not changed."
  }else{Stop-Sync -Outcome what-if -Message 'WhatIf mode: update assessed but not applied.'}
  return
 }
 # Target branch is not checked out in a worktree: compare-and-swap only its ref.
 if($PSCmdlet.ShouldProcess("local $Branch reference",'Fast-forward to fetched remote')){
  $null=Invoke-GitQuiet @('update-ref',$localRef,$remoteSha,$localSha)
  if($script:GitExitCode -ne 0){Stop-Sync -Outcome manual -Message 'Local target changed during sync; safe reference update refused.'; return}
  Stop-Sync -Outcome updated -Message "Local $Branch reference fast-forwarded. Active branch and files were untouched."
 }else{Stop-Sync -Outcome what-if -Message 'WhatIf mode: update assessed but not applied.'}
}catch{
 if($_.Exception.Data.Contains('EchoSyncExitCode')){$script:SyncExitCode=[int]$_.Exception.Data['EchoSyncExitCode']}
 else{Stop-Sync -Outcome error -Message 'Sync stopped safely. Check repository path, Git installation, and permissions; details are not written to the log.'; $script:SyncExitCode=1}
}finally{if($lockStream){$lockStream.Dispose()}}
if($script:SyncExitCode -ne 0){exit $script:SyncExitCode}