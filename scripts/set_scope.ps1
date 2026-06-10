# scripts/set_scope.ps1  — set the authorized scope allowlist (fail-closed until set)
param([Parameter(Mandatory = $true)][string]$Scope)
aws ssm put-parameter --name /tier2/scope-allowlist --type StringList `
    --overwrite --value "$Scope"
Write-Host "Scope allowlist set to: $Scope"
