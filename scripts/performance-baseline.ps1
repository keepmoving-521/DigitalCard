param(
    [string]$BaseUrl = "http://localhost:8000",
    [int]$Requests = 100,
    [double]$P95LimitMs = 500
)
$ErrorActionPreference = "Stop"
$durations = @()
for ($index = 0; $index -lt $Requests; $index++) {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $response = Invoke-WebRequest -UseBasicParsing "$BaseUrl/api/v1/health"
    $watch.Stop()
    if ($response.StatusCode -ne 200) { throw "Health request failed: $($response.StatusCode)" }
    $durations += $watch.Elapsed.TotalMilliseconds
}
$sorted = $durations | Sort-Object
$position = [Math]::Max(0, [Math]::Ceiling($sorted.Count * 0.95) - 1)
$p95 = $sorted[$position]
$average = ($durations | Measure-Object -Average).Average
Write-Host ("Requests={0} Average={1:N2}ms P95={2:N2}ms Limit={3:N2}ms" -f $Requests, $average, $p95, $P95LimitMs)
if ($p95 -gt $P95LimitMs) { throw "Performance baseline failed" }
