$BASE = "http://127.0.0.1:8000"
$tests = @(
    @("Root /",               "/"),
    @("Health /health",       "/health"),
    @("Market BBCA,BBRI",     "/api/market?symbols=BBCA.JK,BBRI.JK"),
    @("Top Movers",           "/api/market/movers"),
    @("Market Overview",      "/api/market/overview"),
    @("Symbol Info BBCA",     "/api/market/info/BBCA.JK"),
    @("Historical BBCA",      "/api/market/historical/BBCA.JK"),
    @("Chat Stats",           "/api/chat/stats"),
    @("Watchlist",            "/api/market/watchlist"),
    @("Market All",           "/api/market/all"),
    @("News (fast)",          "/api/news"),
    @("News by symbol BBCA",  "/api/news/BBCA.JK"),
    @("IHSG",                 "/api/market/ihsg"),
    @("404 Test",             "/api/nonexistent")
)

Write-Host "`n===== NUSATERMINAL QUICK API TEST =====" -ForegroundColor Cyan

foreach ($t in $tests) {
    $label = $t[0]
    $path  = $t[1]
    $url   = $BASE + $path
    $start = Get-Date
    try {
        $r   = Invoke-WebRequest -Uri $url -TimeoutSec 12 -ErrorAction Stop
        $ms  = [math]::Round(((Get-Date) - $start).TotalMilliseconds)
        $len = $r.Content.Length
        Write-Host ("[PASS] $label => HTTP $($r.StatusCode) | ${ms}ms | ${len} bytes") -ForegroundColor Green
    } catch {
        $ms   = [math]::Round(((Get-Date) - $start).TotalMilliseconds)
        $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { "TIMEOUT" }
        $msg  = $_.Exception.Message.Split("`n")[0]
        Write-Host ("[FAIL] $label => $code | ${ms}ms | $msg") -ForegroundColor Red
    }
}

Write-Host "`n=====================================" -ForegroundColor Cyan
