$BASE = "http://localhost:52060"

function Fetch($label, $url) {
    Write-Host "`n--- $label ---" -ForegroundColor Cyan
    try {
        $r = Invoke-WebRequest -Uri $url -TimeoutSec 8 -ErrorAction Stop
        $r.Content | ConvertFrom-Json | ConvertTo-Json -Depth 3
    } catch {
        Write-Host "FAIL: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Fetch "Root"                    "$BASE/"
Fetch "Health"                  "$BASE/health"
Fetch "Companies (limit 3)"     "$BASE/companies?limit=3"
Fetch "BBCA Detail"             "$BASE/companies/BBCA"
Fetch "Market Indices"          "$BASE/market/indices?limit=5"
Fetch "BBCA Trading Daily"      "$BASE/trading/company/BBCA/daily?limit=5"
Fetch "BBCA Trading Summary"    "$BASE/trading/company/BBCA/summary?limit=5"
Fetch "Stock Screener (limit 3)" "$BASE/stock-screener?limit=3"
Fetch "Securities (limit 3)"    "$BASE/securities?limit=3"
