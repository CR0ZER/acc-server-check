#!/usr/bin/env python3

"""
@author: https://github.com/CR0ZER
@license: MIT License
@description: Assetto Corsa Competizione (ACC) Server Status Monitor
    This script monitors the status of Assetto Corsa Competizione server and sends discord notifications
    This script uses the https://acc-status.jonatan.net/ API by Jonatan Wackström
"""

# Standard library imports
from datetime import datetime, timezone
import json
import os
import time
from typing import Dict, Any, Optional

# Third-party imports
import requests


class ACCStatusMonitor:
    def __init__(self):
        self.config = {
            'acc_api_url': 'https://acc-status.jonatan.net/api/v2/acc/status',
            # ACC alert thresholds
            'max_acceptable_ping': 150, # ms - Maximum acceptable ping
            'min_servers_expected': 1000, # Minimum number of servers online
            'max_data_age_minutes': 15, # minutes - Maximum age of data in minutes to consider it valid
            # ACC warning thresholds
            'warning_ping': 100, # ms - Ping threshold for warning
            'warning_servers': 1200, # Minimum number of servers online for warning
            # General config
            'timeout': 15,
            'user_agent': 'ACC-Monitor/1.0 (GitHub Actions)',
            'discord_webhook': os.getenv('DISCORD_WEBHOOK_URL'),
            # Timing API
            'api_update_interval': 5, # minutes
            'api_delay_offset': 30 # seconds - Delay after API update to avoid caching issues
        }
        self.status_file = 'acc_last_status.txt'
        self.metrics_file = 'acc_metrics.json'


    def fetch_api_data(self) -> Dict[str, Any]:
        """
        Fetch data from the ACC status API
        Returns:
            dict: Parsed JSON response from the API
        """
        try:
            self.log(f"Fetching data from {self.config['acc_api_url']}")

            headers = {
                'User-Agent': self.config['user_agent'],
                'Accept': 'application/json',
                'Cache-Control': 'no-cache'
            }

            start_time = time.time()
            response = requests.get(
                self.config['acc_api_url'],
                headers=headers,
                timeout=self.config['timeout']
            )
            response_time = time.time() - start_time

            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f"API HTTP {response.status_code} - {response.reason}",
                    'timestamp': datetime.now().isoformat()
                }
            
            # Parse JSON response
            api_data = response.json()
            api_data['_request_time'] = response_time
            api_data['_fetched_at'] = datetime.now().isoformat()
            api_data['success'] = True

            self.log(f"API data received: status={api_data.get('status')}, ping={api_data.get('ping')}ms")
            return api_data

        except requests.exceptions.Timeout:
            return self.create_api_error("API timeout")
        except requests.exceptions.ConnectionError:
            return self.create_api_error("API connection error")
        except json.JSONDecodeError:
            return self.create_api_error("API response is not valid JSON")
        except Exception as e:
            return self.create_api_error(f"Unexpected error: {str(e)}")


    def create_api_error(self, reason: str) -> Dict[str, Any]:
        """
        Create a standardized error response for API errors
        Args:
            message (str): Error message to include in the response
        Returns:
            dict: Error response with success=False and error message
        """
        return {
            'success': False,
            'error': reason,
            'timestamp': datetime.now().isoformat(),
            'status': None,
            'ping': None,
            'servers': None,
            'players': None
        }


    def analyze_acc_status(self, api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the ACC status data and determine server status
        Args:
            api_data (dict): Parsed JSON response from the API
        Returns:
            analysis (dict): Analysis results
        """
        if not api_data.get('success', False):
            return {
                'status': 'API_ERROR',
                'reason': api_data.get('error', 'API error'),
                'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                'source': 'api_error'
            }

        # Extract main data
        api_status = api_data.get('status')  # 1=up, 0==down, -1=unknown
        ping = api_data.get('ping')  # int or null
        servers = api_data.get('servers', 0) 
        players = api_data.get('players', 0)
        date_str = api_data.get('date')
        down_since = api_data.get('down_since')

        data_age_minutes = 0
        if date_str:
            try:
                data_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                utc_current = datetime.now(timezone.utc)
                data_age = utc_current - data_date
                data_age_minutes = data_age.total_seconds() / 60
            except:
                data_age_minutes = 999  # Parse error - old data

        analysis = {
            'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            'source': 'acc_api',
            'api_status': api_status,
            'ping_ms': ping,
            'servers_count': servers,
            'players_count': players,
            'data_age_minutes': round(data_age_minutes, 1),
            'down_since': down_since,
            'api_response_time': api_data.get('_request_time', 0)
        }

        # Determine final status
        analysis['status'] = self.determine_overall_status(analysis)
        analysis['issues'] = self.identify_issues(analysis)

        return analysis


    def determine_overall_status(self, analysis: Dict[str, Any]) -> str:
        """
        Determine the overall status based on analysis results
        Args:
            analysis (dict): Analysis results from analyze_acc_status
        Returns:
            str: Overall status
        """
        api_status = analysis['api_status']
        ping = analysis['ping_ms']
        servers = analysis['servers_count']
        data_age = analysis['data_age_minutes']

        if api_status == 0:  # Server is down
            return 'DOWN'
        elif api_status == -1:  # Unknown status
            return 'UNKNOWN'
        elif api_status != 1:  # Unexpected status
            return 'API_ERROR'
        
        # API is up - check metrics
        issues = []

        if ping is None:
            issues.append("ping_null")
        elif ping > self.config['max_acceptable_ping']:
            issues.append("ping_high")

        if servers < self.config['min_servers_expected']:
            issues.append("servers_low")

        if data_age > self.config['max_data_age_minutes']:
            issues.append("data_old")

        # Determine final status
        if not issues:
            return 'UP'
        elif len(issues) == 1 and issues[0] not in ['ping_null', 'data_old']:
            return 'DEGRADED'  # Single issue that is not critical
        else:
            return 'DOWN'  # Multiple issues or critical issues


    def identify_issues(self, analysis: Dict[str, Any]) -> list:
        """
        Identify specific issues based on analysis results
        Args:
            analysis (dict): Analysis results from analyze_acc_status
        Returns:
            issues (list): List of identified issues
        """
        issues = []

        api_status = analysis['api_status']
        ping = analysis['ping_ms']
        servers = analysis['servers_count']
        data_age = analysis['data_age_minutes']

        # Server down or unknown
        if api_status == 0:
            issues.append("ACC servers offline (API)")
        elif api_status == -1:
            issues.append("ACC servers status unknown (API)")

        # Performance issues
        if ping is None and api_status == 1:
            issues.append("ACC ping unavailable")
        elif ping and ping > self.config['max_acceptable_ping']:
            issues.append(f"ACC ping high: {ping}ms (> {self.config['max_acceptable_ping']}ms)")
        elif ping and ping > self.config['warning_ping']:
            issues.append(f"ACC ping warning: {ping}ms (> {self.config['warning_ping']}ms)")

        # Server count issues
        if servers < self.config['min_servers_expected']:
            issues.append(f"ACC servers count low: {servers} (< {self.config['min_servers_expected']})")
        elif servers < self.config['warning_servers']:
            issues.append(f"ACC servers count decreasing ({servers})")

        # Data age issues
        if data_age > self.config['max_data_age_minutes']:
            issues.append(f"ACC data too old: {data_age} minutes (> {self.config['max_data_age_minutes']} minutes)")

        return issues


    def create_discord_embed(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a Discord embed message
        Args:
            analysis (dict): Analysis results from analyze_acc_status
        Returns:
            embed (dict): Discord embed message structure
        """
        status = analysis['status']
        api_status = analysis['api_status']

        # Visual
        if status == 'UP':
            color = 0x28A745
            emoji = "🟢"
            title = "🏎️ ACC SERVERS ONLINE"
        elif status == 'DEGRADED':
            color = 0xFFC107
            emoji = "🟠"
            title = "🏎️ ACC SERVERS DEGRADED"
        elif status == 'DOWN':
            color = 0xDC3545
            emoji = "🔴"
            title = "🏎️ ACC SERVERS OFFLINE"
        elif status == 'UNKNOWN':
            color = 0x6C757D
            emoji = "❓"
            title = "🏎️ ACC SERVERS UNKNOWN"
        elif status == 'API_ERROR':
            color = 0x6610F2
            emoji = "⚠️"
            title = "🏎️ ACC API ERROR"

        embed = {
            'embeds': [{
                'title': f'{emoji} {title}',
                'color': color,
                'timestamp': datetime.now().isoformat(),
                'url': 'https://acc-status.jonatan.net/',
                'fields': [
                    {
                        'name': '📊 State Detected',
                        'value': f'`{status}`',
                        'inline': True
                    },
                    {
                        'name': '🤖 API Status',
                        'value': f'`{api_status}` {'(UP)' if api_status == 1 else '(DOWN)' if api_status == 0 else '(UNKNOWN)' if api_status == -1 else '(ERROR)'}',
                        'inline': True
                    },
                    {
                        'name': '📅 Last Update',
                        'value': analysis['timestamp'],
                        'inline': True
                    }
                ],
                'footer': {
                    'text': 'ACC API Status Monitor • Official Data Source: https://acc-status.jonatan.net/',
                    "icon_url": "https://cdn.cloudflare.steamstatic.com/steam/apps/805550/header.jpg"
                    # 'icon_url': 'https://sm.ign.com/ign_fr/cover/a/assetto-co/assetto-corsa-competizione_g2pf.jpg'
                }
            }]
        }

        # Add ping field if available
        if analysis['ping_ms'] is not None:
            ping = analysis['ping_ms']
            ping_status = "🟢" if ping <= self.config['warning_ping'] else "🟡" if ping <= self.config['max_acceptable_ping'] else "🔴"
            embed['embeds'][0]['fields'].append({
                'name': f'{ping_status} Ping Servers',
                'value': f'`{ping} ms`',
                'inline': True
            })
        # Add servers count field
        if analysis['servers_count'] is not None:
            servers = analysis['servers_count']
            servers_status = "🟢" if servers >= self.config['warning_servers'] else "🟡" if servers >= self.config['min_servers_expected'] else "🔴"
            embed['embeds'][0]['fields'].append({
                'name': f'{servers_status} Servers Online',
                'value': f'`{servers:,}`',
                'inline': True
            })
        # Add players count field
        if analysis['players_count'] is not None:
            players = analysis['players_count']
            embed['embeds'][0]['fields'].append({
                'name': '👥 Players Online',
                'value': f'`{players:,}`',
                'inline': True
            })
        # Add data age field
        data_age = analysis.get('data_age_minutes', 0)
        age_status = "🟢" if data_age <= self.config['max_data_age_minutes'] else "🔴"
        embed['embeds'][0]['fields'].append({
            'name': f'{age_status} Data Age',
            'value': f'`{data_age:.1f} minutes ago`',
            'inline': True
        })
        # Time response API field
        if 'api_response_time' in analysis:
            response_time = analysis['api_response_time']
            embed['embeds'][0]['fields'].append({
                'name': '⏱️ API Response Time',
                'value': f'`{response_time:.2f}s`',
                'inline': True
            })
        # Add issues field if any
        issues = analysis.get('issues', [])
        if issues:
            issues_text = "\n".join([f"• {issue}" for issue in issues[:5]])
            embed['embeds'][0]['fields'].append({
                'name': '⚠️ Issues Detected',
                'value': f'```\n{issues_text}```',
                'inline': False
            })
        # Add offline info field if possible
        if analysis.get('down_since'):
            try:
                down_date = datetime.fromisoformat(analysis['down_since'].replace('Z', '+00:00'))
                down_duration = datetime.now().replace(tzinfo=down_date.tzinfo) - down_date
                hours = int(down_duration.total_seconds() // 3600)
                minutes = int((down_duration.total_seconds() % 3600) // 60)

                embed['embeds'][0]['fields'].append({
                    'name': '⏳ Duration Offline',
                    'value': f'`{hours}h {minutes}min`',
                    'inline': True
                })
            except:
                pass

        return embed


    def send_discord_notification(self, analysis: Dict[str, Any]) -> bool:
        """
        Send a notification to Discord
        Args:
            analysis (dict): Analysis results from analyze_acc_status
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        if not self.config['discord_webhook']:
            self.log("No Discord webhook URL configured, skipping notification")
            return False

        try:
            embed = self.create_discord_embed(analysis)

            response = requests.post(
                self.config['discord_webhook'],
                json=embed,
                headers={'Content-Type': 'application/json'},
                timeout=self.config['timeout']
            )

            if response.status_code == 204:
                self.log("Discord notification sent successfully")
                return True
            else:
                self.log(f"Failed to send Discord notification: HTTP {response.status_code} - {response.reason}")
                return False

        except Exception as e:
            self.log(f"Error sending Discord notification: {str(e)}")
            return False
    

    def save_metrics_history(self, analysis: Dict[str, Any]) -> None:
        """
        Save the analysis results to a metrics history file
        Args:
            analysis (dict): Analysis results from analyze_acc_status
        """
        try:
            history = []
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            history.append(analysis)

            history = history[-200:]  # Keep only the last 200 entries - ~17h of data

            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)

            self.log(f"Metrics history saved to {self.metrics_file} ({len(history)} entries)")

        except Exception as e:
            self.log(f"Error saving metrics history: {str(e)}")


    def get_last_status(self) -> Optional[str]:
        """
        Load the last status from the status file
        Returns:
            str: Last status or None if file does not exist
        """
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
        except:
            pass
        return None
    

    def save_status(self, status: str) -> None:
        """
        Save the current status
        Args:
            status (str): Current status to save
        """
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                f.write(status)
        except Exception as e:
            self.log(f"Error saving status: {str(e)}")


    def log(self, message: str) -> None:
        """
        Log a message to the console with a timestamp
        Args:
            message (str): Message to log
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    

    def run(self) -> Dict[str, Any]:
        """
        Main method to run the ACC status monitor
        Returns:
            analysis (dict): Final analysis results
        """
        self.log("Starting ACC Status Monitor")
        self.log("=" * 60)

        api_data = self.fetch_api_data()

        analysis = self.analyze_acc_status(api_data)

        last_status = self.get_last_status()
        current_status = analysis['status']

        self.log(f"Current status: {current_status}")
        self.log(f"Last status: {last_status or 'Unknown'}")

        # Print main metrics
        if analysis.get('ping_ms') is not None:
            self.log(f"Ping: {analysis['ping_ms']}ms")
        if analysis.get('servers_count') is not None:
            self.log(f"Servers: {analysis['servers_count']:,}")
        if analysis.get('players_count') is not None:
            self.log(f"Players: {analysis['players_count']:,}")
        if analysis.get('data_age_minutes') is not None:
            self.log(f"Data age: {analysis['data_age_minutes']:.1f} min")
        
        issues = analysis.get('issues', [])
        if issues:
            self.log(f"Issues detected: {', '.join(issues)}")
        
        significant_change = (
            last_status is None or  # First run, no last status
            last_status != current_status or  # Status changed
            current_status in ['DOWN', 'API_ERROR'],  # Critical status
            os.getenv('FORCE_NOTIFICATION', 'false').lower() == 'true'
        )

        if significant_change:
            if last_status is None:
                self.log("First API monitoring")
            elif last_status != current_status:
                self.log(f"Status change: {last_status} → {current_status}")
            else:
                self.log(f"Critical status detected: {current_status}")
            
            # Send Discord notification
            if self.send_discord_notification(analysis):
                self.save_status(current_status)
                self.log("Status saved to file")
            else:
                self.log("Failed to send Discord notification, status not saved")
        else:
            self.log("No significant status change, skipping notification")

        # Save metrics history
        self.save_metrics_history(analysis)

        self.log("=" * 60)
        self.log("ACC Status Monitor finished")

        return analysis


def main():
    monitor = ACCStatusMonitor()

    try:
        result = monitor.run()

        if result.get('status') in ['UP', 'DEGRADED', 'DOWN']:
            exit(0)
        else:
            exit(1)

    except KeyboardInterrupt:
        monitor.log("Monitoring interrupted by user")
        exit(130)
    except Exception as e:
        monitor.log(f"Unexpected error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()