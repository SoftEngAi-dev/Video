"""
Digital clock displaying current time in multiple time zones.
Supports real-time updates via browser WebSocket or refresh.
"""

import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

# Common time zones for display
DEFAULT_ZONES = [
    ("UTC", "UTC"),
    ("Eastern", "America/New_York"),
    ("Central", "America/Chicago"),
    ("Mountain", "America/Denver"),
    ("Pacific", "America/Los_Angeles"),
    ("London", "Europe/London"),
    ("Paris", "Europe/Paris"),
    ("Tokyo", "Asia/Tokyo"),
    ("Sydney", "Australia/Sydney"),
]


def get_time_zones(zones=None):
    """
    Get current time in specified time zones.
    
    Args:
        zones: List of (display_name, tz_identifier) tuples.
               Defaults to DEFAULT_ZONES.
    
    Returns:
        List of dicts with zone info and current time.
    """
    if zones is None:
        zones = DEFAULT_ZONES
    
    result = []
    now_utc = datetime.datetime.now(datetime.UTC)
    
    for display_name, tz_id in zones:
        try:
            tz = ZoneInfo(tz_id)
            local_time = now_utc.astimezone(tz)
            result.append({
                "zone": display_name,
                "tz_id": tz_id,
                "time": local_time.strftime("%H:%M:%S"),
                "date": local_time.strftime("%Y-%m-%d"),
                "offset": local_time.strftime("%z"),
            })
        except Exception as e:
            result.append({
                "zone": display_name,
                "tz_id": tz_id,
                "error": str(e),
            })
    
    return result


def generate_html(zones=None):
    """
    Generate standalone HTML clock display.
    """
    if zones is None:
        zones = DEFAULT_ZONES
    
    zones_json = json.dumps(zones)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Global Time Zones Clock</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Monaco', 'Courier New', monospace;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: #e0e0e0;
        }}
        
        .container {{
            width: 100%;
            max-width: 1200px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #22d3ee, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .header p {{
            font-size: 0.9rem;
            color: #999;
        }}
        
        .clocks {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .clock {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 24px;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        }}
        
        .clock:hover {{
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(170, 139, 250, 0.3);
            box-shadow: 0 12px 48px rgba(170, 139, 250, 0.2);
        }}
        
        .clock-zone {{
            font-size: 0.9rem;
            color: #22d3ee;
            margin-bottom: 8px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        
        .clock-tz {{
            font-size: 0.75rem;
            color: #999;
            margin-bottom: 12px;
        }}
        
        .clock-time {{
            font-size: 2rem;
            font-weight: bold;
            color: #fff;
            margin-bottom: 8px;
            font-variant-numeric: tabular-nums;
            letter-spacing: 2px;
        }}
        
        .clock-date {{
            font-size: 0.85rem;
            color: #ccc;
            margin-bottom: 8px;
        }}
        
        .clock-offset {{
            font-size: 0.8rem;
            color: #a78bfa;
            padding-top: 8px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .refresh-btn {{
            background: linear-gradient(90deg, #22d3ee, #a78bfa);
            border: none;
            color: white;
            padding: 12px 24px;
            font-size: 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
            display: block;
            margin: 0 auto;
        }}
        
        .refresh-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(34, 211, 238, 0.3);
        }}
        
        .refresh-btn:active {{
            transform: translateY(0);
        }}
        
        .update-time {{
            text-align: center;
            margin-top: 20px;
            font-size: 0.8rem;
            color: #666;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8rem;
            }}
            
            .clock-time {{
                font-size: 1.5rem;
            }}
            
            .clocks {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⏰ Global Time Zones</h1>
            <p>Real-time clock display across major time zones</p>
        </div>
        
        <div class="clocks" id="clocks"></div>
        
        <button class="refresh-btn" onclick="updateClocks()">Refresh Now</button>
        
        <div class="update-time">
            <span id="lastUpdate">Last updated: just now</span>
        </div>
    </div>
    
    <script>
        const ZONES = {zones_json};
        let lastUpdateTime = Date.now();
        
        function formatTimeAgo(ms) {{
            const now = Date.now();
            const seconds = Math.floor((now - ms) / 1000);
            
            if (seconds < 60) return 'just now';
            const minutes = Math.floor(seconds / 60);
            if (minutes < 60) return `${{minutes}}m ago`;
            const hours = Math.floor(minutes / 60);
            return `${{hours}}h ago`;
        }}
        
        function updateClocks() {{
            const clocksContainer = document.getElementById('clocks');
            clocksContainer.innerHTML = '';
            
            // Simulate local time calculation based on timezone data
            const now = new Date();
            const zones = ZONES;
            
            zones.forEach(([displayName, tzId]) => {{
                const clockDiv = document.createElement('div');
                clockDiv.className = 'clock';
                
                // Format time using Intl API
                const formatter = new Intl.DateTimeFormat('en-US', {{
                    timeZone: tzId,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false,
                }});
                
                const dateFormatter = new Intl.DateTimeFormat('en-US', {{
                    timeZone: tzId,
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                }});
                
                const time = formatter.format(now);
                const date = dateFormatter.format(now);
                
                // Calculate offset
                const utcDate = new Date(now.toLocaleString('en-US', {{ timeZone: 'UTC' }}));
                const tzDate = new Date(now.toLocaleString('en-US', {{ timeZone: tzId }}));
                const offsetMs = tzDate - utcDate;
                const offsetHours = Math.floor(offsetMs / 3600000);
                const offsetMinutes = Math.abs((offsetMs % 3600000) / 60000);
                const offsetStr = `UTC${{offsetHours >= 0 ? '+' : ''}}${{offsetHours}}:${{String(offsetMinutes).padStart(2, '0')}}`;
                
                clockDiv.innerHTML = `
                    <div class="clock-zone">${{displayName}}</div>
                    <div class="clock-tz">${{tzId}}</div>
                    <div class="clock-time">${{time}}</div>
                    <div class="clock-date">${{date}}</div>
                    <div class="clock-offset">${{offsetStr}}</div>
                `;
                
                clocksContainer.appendChild(clockDiv);
            }});
            
            lastUpdateTime = Date.now();
            document.getElementById('lastUpdate').textContent = 
                'Last updated: ' + formatTimeAgo(lastUpdateTime);
        }}
        
        // Initial load
        updateClocks();
        
        // Update every second
        setInterval(updateClocks, 1000);
        
        // Update "last updated" text every 10 seconds
        setInterval(() => {{
            document.getElementById('lastUpdate').textContent = 
                'Last updated: ' + formatTimeAgo(lastUpdateTime);
        }}, 10000);
    </script>
</body>
</html>"""
    
    return html


def save_clock_app(output_dir, zones=None):
    """
    Save clock app to output directory.
    
    Args:
        output_dir: Path to save index.html
        zones: List of (display_name, tz_identifier) tuples.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    html = generate_html(zones)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    
    # Also save zone data as JSON for API use
    zones_data = get_time_zones(zones)
    (output_dir / "zones.json").write_text(
        json.dumps(zones_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate global time zone clock")
    parser.add_argument(
        "--output",
        type=str,
        default="clock_output",
        help="Output directory for HTML file"
    )
    parser.add_argument(
        "--zones",
        type=str,
        nargs="+",
        help="Custom timezone identifiers (e.g., Asia/Tokyo Europe/Berlin)"
    )
    
    args = parser.parse_args()
    
    custom_zones = None
    if args.zones:
        custom_zones = [(tz, tz) for tz in args.zones]
    
    save_clock_app(args.output, custom_zones or DEFAULT_ZONES)
    print(f"Clock app generated at {args.output}/index.html")
    
    # Print current times
    print("\nCurrent time in all zones:")
    for zone_info in get_time_zones(custom_zones or DEFAULT_ZONES):
        if "error" not in zone_info:
            print(f"  {zone_info['zone']:12} {zone_info['time']} {zone_info['offset']}")
