# Registers the daily Windows scheduled task for the Kaggle autopilot.
# Run once:  powershell -ExecutionPolicy Bypass -File deploy\kaggle_autopilot\register_task.ps1

$script = "C:\Users\HP\Downloads\livejepa_repo\livejepa_repo\deploy\kaggle_autopilot\run_daily.ps1"
schtasks /Create /F /SC DAILY /ST 06:00 /TN "LiveJEPA_KaggleAutopilot" `
    /TR "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
schtasks /Query /TN "LiveJEPA_KaggleAutopilot" /V /FO LIST | Select-String "TaskName|Next Run Time|Status"
