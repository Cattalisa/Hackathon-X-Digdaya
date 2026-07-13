$BASE = "http://127.0.0.1:8000"
$results = @()

function Test-Endpoint {
    param($method, $url, $body = $null, $label = $null)
    if (-not $label) { $label = "$method $url" }
    try {
        $start = Get-Date
        if ($method -eq "POST" -and $body) {
            $resp = Invoke-WebRequest -Uri $url -Method $method -Body ($body | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 30 -ErrorAction Stop
        } else {
            $resp = Invoke-WebRequest -Uri $url -Method $method -TimeoutSec 30 -ErrorAction Stop
        }
        $elapsed = ((Get-Date) - $start).TotalSeconds
        $preview = ($resp.Content | ConvertFrom-Json -ErrorAction SilentlyContinue | ConvertTo-Json -Depth 1 -Compress) 
        if ($preview.Length -gt 200) { $preview = $preview.Substring(0,200) + "..." }
        return [PSCustomObject]@{ Label=$label; Status=$resp.StatusCode; Time=[math]::Round($elapsed,2); Result="OK"; Preview=$preview }
    } catch {
        $elapsed = ((Get-Date) - $start).TotalSeconds
        $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
        return [PSCustomObject]@{ Label=$label; Status=$code; Time=[math]::Round($elapsed,2); Result="FAIL"; Preview=$_.Exception.Message }
    }
}

$results += Test-Endpoint "GET" "$BASE/" -label "Root /"
$results += Test-Endpoint "GET" "$BASE/health" -label "Health /health"
$results += Test-Endpoint "GET" "$BASE/api/market?symbols=BBCA.JK,BBRI.JK" -label "Market (BBCA,BBRI)"
$results += Test-Endpoint "GET" "$BASE/api/market/movers" -label "Market Movers"
$results += Test-Endpoint "GET" "$BASE/api/market/all" -label "Market All"
$results += Test-Endpoint "GET" "$BASE/api/market/overview" -label "Market Overview"
$results += Test-Endpoint "GET" "$BASE/api/market/watchlist" -label "Watchlist"
$results += Test-Endpoint "GET" "$BASE/api/market/info/BBCA.JK" -label "Symbol Info BBCA"
$results += Test-Endpoint "GET" "$BASE/api/market/ihsg" -label "IHSG Data"
$results += Test-Endpoint "GET" "$BASE/api/market/historical/BBCA.JK" -label "Historical BBCA"
$results += Test-Endpoint "GET" "$BASE/api/market/historical/BBCA.JK?period=1mo" -label "Historical BBCA 1mo"
$results += Test-Endpoint "GET" "$BASE/api/market/historical/FAKESYM.JK" -label "Historical 404 test"
$results += Test-Endpoint "GET" "$BASE/api/news" -label "News (all)"
$results += Test-Endpoint "GET" "$BASE/api/news?limit=5" -label "News (limit=5)"
$results += Test-Endpoint "GET" "$BASE/api/news/BBCA.JK" -label "News by symbol BBCA"
$results += Test-Endpoint "GET" "$BASE/api/sentiment?symbols=BBCA.JK" -label "Sentiment BBCA"
$results += Test-Endpoint "GET" "$BASE/api/sentiment/BBCA.JK" -label "Sentiment detail BBCA"
$results += Test-Endpoint "GET" "$BASE/api/signals?symbols=BBCA.JK" -label "Quant Signal BBCA"
$results += Test-Endpoint "GET" "$BASE/api/signals/BBCA.JK" -label "Quant Signal detail BBCA"
$results += Test-Endpoint "GET" "$BASE/api/chat/stats" -label "Chat stats"
$results += Test-Endpoint "POST" "$BASE/api/chat" -body @{user_id="test"; message="Bagaimana kondisi saham BBCA?"} -label "Chat POST"
$results += Test-Endpoint "GET" "$BASE/api/nonexistent" -label "404 unknown route"

Write-Output "`n===== NUSATERMINAL API TEST REPORT =====`n"
$results | ForEach-Object {
    $status = if ($_.Result -eq "OK") { "[PASS]" } else { "[FAIL]" }
    Write-Output "$status $($_.Label) => HTTP $($_.Status) | $($_.Time)s"
}

Write-Output "`n===== RESPONSE PREVIEWS =====`n"
$results | ForEach-Object {
    Write-Output "--- $($_.Label) ---"
    Write-Output "$($_.Preview)"
    Write-Output ""
}

$pass = ($results | Where-Object { $_.Result -eq "OK" }).Count
$fail = ($results | Where-Object { $_.Result -eq "FAIL" }).Count
Write-Output "`n===== SUMMARY: $pass PASS / $fail FAIL / $($results.Count) TOTAL =====`n"
