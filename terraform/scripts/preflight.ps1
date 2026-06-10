param(
    [ValidateSet("dev", "prod", "all")]
    [string]$Environment = "all"
)

$ErrorActionPreference = "Stop"

$tenantId = "83474cb5-f1fa-4d06-906c-e5dad12ce3b9"
$environments = [ordered]@{
    dev = @{
        SubscriptionId = "6b01db76-626a-44a2-8119-17682410914a"
        Location       = "southindia"
        VmSizes        = @("Standard_D2as_v5")
        PostgreSqlSku  = "Standard_B2ms"
    }
    prod = @{
        SubscriptionId = "a8270be7-dabc-4d92-98db-26a55025b0df"
        Location       = "centralindia"
        VmSizes        = @("Standard_D2as_v5", "Standard_D4as_v5")
        PostgreSqlSku  = "Standard_D2ds_v5"
    }
}

$targets = if ($Environment -eq "all") {
    $environments.Keys
}
else {
    @($Environment)
}

foreach ($name in $targets) {
    $config = $environments[$name]
    Write-Host "Checking $name subscription $($config.SubscriptionId)"

    $account = az account show `
        --subscription $config.SubscriptionId `
        --query "{id:id,tenantId:tenantId,name:name}" `
        -o json | ConvertFrom-Json

    if ($LASTEXITCODE -ne 0 -or -not $account) {
        throw "The current Azure CLI login cannot access the $name subscription."
    }
    if ($account.tenantId -ne $tenantId) {
        throw "$name is authenticated against tenant $($account.tenantId), expected $tenantId."
    }

    foreach ($vmSize in $config.VmSizes) {
        $sku = az vm list-skus `
            --subscription $config.SubscriptionId `
            --location $config.Location `
            --resource-type virtualMachines `
            --all `
            --query "[?name=='$vmSize'] | [0]" `
            -o json | ConvertFrom-Json

        if (-not $sku) {
            throw "$vmSize was not returned for $($config.Location)."
        }

        $locationRestriction = $sku.restrictions |
            Where-Object {
                $_.type -eq "Location" -and
                $_.reasonCode -eq "NotAvailableForSubscription"
            }

        if ($locationRestriction) {
            throw "$vmSize is unavailable for $name in $($config.Location)."
        }
    }

    $postgres = az postgres flexible-server list-skus `
        --subscription $config.SubscriptionId `
        --location $config.Location `
        -o json | ConvertFrom-Json

    if (-not $postgres -or $postgres[0].reason) {
        throw "PostgreSQL provisioning is restricted for $name in $($config.Location): $($postgres[0].reason)"
    }

    $postgresSku = $postgres[0].supportedServerEditions.supportedServerSkus |
        Where-Object { $_.name -eq $config.PostgreSqlSku } |
        Select-Object -First 1

    if (-not $postgresSku) {
        throw "PostgreSQL SKU $($config.PostgreSqlSku) is unavailable for $name."
    }

    Write-Host "$name preflight passed." -ForegroundColor Green
}
