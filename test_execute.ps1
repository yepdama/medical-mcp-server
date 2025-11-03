# Test MCP Execute Endpoint
$baseUrl = "http://localhost:8000"
$token = "super-secret-token"

Write-Host "=== Testing MCP Execute ===" -ForegroundColor Green

# Check health
Write-Host "Checking server..."
try {
    $health = Invoke-RestMethod -Uri "$baseUrl/healthz" -ErrorAction Stop
    Write-Host "Server OK: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "Server not reachable! Start server first with: python main.py" -ForegroundColor Red
    exit 1
}

# Prepare request
$requestId = [guid]::NewGuid().ToString()
Write-Host "Request ID: $requestId"

$requestBody = @{
    tool = "openai_chat"
    input = @{
        messages = @(
            @{
                role = "system"
                content = "You are a medical assistant."
            },
            @{
                role = "user"
                content = "What is fever?"
            }
        )
    }
    session_id = "poc-convo-1"
    request_id = $requestId
}

$jsonBody = $requestBody | ConvertTo-Json -Depth 10

# Execute
Write-Host "`nSending request..."
try {
    $response = Invoke-RestMethod `
        -Uri "$baseUrl/mcp/execute" `
        -Method POST `
        -Headers @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        } `
        -Body $jsonBody `
        -ErrorAction Stop
    
    Write-Host "`n=== SUCCESS ===" -ForegroundColor Green
    Write-Host "Response as JSON:" -ForegroundColor Cyan
    $response | ConvertTo-Json
    
    Write-Host "`nCall ID: $($response.call_id)" -ForegroundColor Yellow
    Write-Host "Status: $($response.status)" -ForegroundColor Yellow
    
    Write-Host "`nTo stream:" -ForegroundColor Cyan
    Write-Host "curl.exe -N -H `"Authorization: Bearer $token`" `"$baseUrl/mcp/stream/$($response.call_id)`""
    
    Write-Host "`nTo cancel all requests:" -ForegroundColor Cyan
    Write-Host "curl.exe -X POST -H `"Authorization: Bearer $token`" `"$baseUrl/mcp/cancel_all`""
    
} catch {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host "Message: $($_.Exception.Message)" -ForegroundColor Red
    
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "Status Code: $statusCode" -ForegroundColor Red
        
        try {
            $errorStream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($errorStream)
            $errorBody = $reader.ReadToEnd()
            Write-Host "Error Body:" -ForegroundColor Red
            Write-Host $errorBody
        } catch {
            Write-Host "Could not read error body" -ForegroundColor Yellow
        }
    }
}
