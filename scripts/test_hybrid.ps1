$BASE = "http://localhost:8000/api"

Write-Host "--- Health ---" -ForegroundColor Cyan
Invoke-RestMethod "http://localhost:8000/health" | ConvertTo-Json

Write-Host "`n--- Market BBCA ---" -ForegroundColor Cyan
Invoke-RestMethod "$BASE/market?symbols=BBCA.JK" | ConvertTo-Json -Depth 2

Write-Host "`n--- Historical BBCA (3mo) ---" -ForegroundColor Cyan
$hist = Invoke-RestMethod "$BASE/market/historical/BBCA.JK?period=3mo"
$hist[0..2] | ConvertTo-Json -Depth 2

Write-Host "`n--- Symbol Info BBCA ---" -ForegroundColor Cyan
Invoke-RestMethod "$BASE/market/info/BBCA.JK" | ConvertTo-Json -Depth 3
