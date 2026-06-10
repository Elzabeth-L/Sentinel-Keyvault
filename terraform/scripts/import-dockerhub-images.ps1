param(
    [Parameter(Mandatory = $true)]
    [string]$AcrName,

    [string]$DockerHubUsername,

    [string]$DockerHubToken
)

$ErrorActionPreference = "Stop"

$images = [ordered]@{
    "sentinel-web"                        = "v1.0.5"
    "sentinel-identity-service"           = "v1.0.3"
    "sentinel-inventory-service"          = "v1.0.5"
    "sentinel-relationship-service"       = "v1.0.0"
    "sentinel-change-intelligence-service" = "v1.0.0"
    "sentinel-operations-service"         = "v1.0.0"
    "sentinel-audit-service"              = "v1.0.0"
    "sentinel-migration"                  = "v1.0.3"
}

foreach ($entry in $images.GetEnumerator()) {
    $source = "docker.io/elzabeth03/$($entry.Key):$($entry.Value)"
    $target = "$($entry.Key):$($entry.Value)"
    $arguments = @(
        "acr", "import",
        "--name", $AcrName,
        "--source", $source,
        "--image", $target,
        "--force"
    )

    if ($DockerHubUsername -and $DockerHubToken) {
        $arguments += @("--username", $DockerHubUsername, "--password", $DockerHubToken)
    }

    Write-Host "Importing $source as $target"
    & az @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Import failed for $source"
    }
}

Write-Host "Imported $($images.Count) images into $AcrName."
