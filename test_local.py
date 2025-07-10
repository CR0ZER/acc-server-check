#!/usr/bin/env python3

"""
@author: https://github.com/CR0ZER
@license: MIT License
@description: Assetto Corsa Competizione (ACC) Server Status Monitor
    This script lets you run the monitor locally without needing to deploy
    This script uses the https://acc-status.jonatan.net/ API by Jonatan Wackström
"""

import sys
import os
import json
import requests
import time
from datetime import datetime, timezone

def test_webhook_format(webhook_url: str) -> bool:
    """Vérifie le format du webhook Discord."""
    if not webhook_url or not webhook_url.startswith('https://discord.com/api/webhooks/'):
        return False
    parts = webhook_url.split('/')
    return len(parts) == 7

def test_acc_api_direct():
    """Teste l'accès direct à l'API ACC."""
    print("🔍 Test accès API ACC")
    print("=" * 30)
    
    api_url = 'https://acc-status.jonatan.net/api/v2/acc/status'
    
    try:
        print(f"📡 Connexion à l'API: {api_url}")
        
        start_time = time.time()
        response = requests.get(api_url, timeout=10)
        response_time = time.time() - start_time
        
        print(f"✅ Réponse reçue en {response_time:.2f}s")
        print(f"📊 Status HTTP: {response.status_code}")
        
        if response.status_code == 200:
            api_data = response.json()
            print("✅ JSON parsé avec succès!")
            
            # Affichage des données principales
            print("\n📋 Données API reçues:")
            important_fields = ['status', 'ping', 'servers', 'players', 'date']
            
            for field in important_fields:
                if field in api_data:
                    value = api_data[field]
                    if field == 'status':
                        status_names = {1: 'UP 🟢', 0: 'DOWN 🔴', -1: 'UNKNOWN 🟡'}
                        print(f"   📊 {field}: {value} ({status_names.get(value, 'INVALID')})")
                    elif field == 'ping':
                        if value is not None:
                            print(f"   🏓 {field}: {value}ms")
                        else:
                            print(f"   🏓 {field}: null (serveurs down)")
                    elif field in ['servers', 'players']:
                        emoji = '🖥️' if field == 'servers' else '👥'
                        print(f"   {emoji} {field}: {value:,}")
                    else:
                        print(f"   🕐 {field}: {value}")
            
            # Affichage des champs supplémentaires
            extra_fields = [k for k in api_data.keys() if k not in important_fields]
            if extra_fields:
                print(f"\n📎 Champs supplémentaires: {', '.join(extra_fields)}")
            
            return api_data, True
        else:
            print(f"❌ Erreur HTTP: {response.status_code}")
            print(f"📄 Réponse: {response.text[:200]}")
            return None, False
            
    except requests.exceptions.Timeout:
        print("❌ Timeout de l'API (>10s)")
        return None, False
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter à l'API")
        return None, False
    except json.JSONDecodeError:
        print("❌ Réponse n'est pas du JSON valide")
        return None, False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return None, False

def test_analysis_logic(api_data):
    """Teste la logique d'analyse sans importer le module principal."""
    print("\n🧠 Test logique d'analyse")
    print("=" * 30)
    
    if not api_data:
        print("❌ Pas de données API à analyser")
        return None
    
    try:
        # Configuration des seuils (copiée du module principal)
        config = {
            'max_acceptable_ping': 200,
            'min_servers_expected': 1000,
            'max_data_age_minutes': 20,  # Plus tolérant (au lieu de 15)
            'warning_ping': 150,
            'warning_servers': 1200,
        }
        
        # Extraction des données principales
        api_status = api_data.get('status')
        ping = api_data.get('ping')
        servers = api_data.get('servers', 0)
        players = api_data.get('players', 0)
        date_str = api_data.get('date')
        
        # Calcul de l'âge des données
        data_age_minutes = 0
        if date_str:
            try:
                data_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                utc_current = datetime.now(timezone.utc)
                data_age = utc_current - data_date
                data_age_minutes = data_age.total_seconds() / 60
                print(f"🕐 Debug âge données:")
                print(f"   Date API: {date_str}")
                print(f"   Maintenant: {datetime.now()}")
                print(f"   Différence: {data_age_minutes:.1f} minutes")
            except Exception as e:
                data_age_minutes = 999
                print(f"❌ Erreur calcul âge: {e}")
        
        # Analyse de l'état
        analysis = {
            'api_status': api_status,
            'ping_ms': ping,
            'servers_count': servers,
            'players_count': players,
            'data_age_minutes': round(data_age_minutes, 1),
            'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }
        
        # Détermination de l'état final
        if api_status == 0:
            status = 'DOWN'
        elif api_status == -1:
            status = 'UNKNOWN'
        elif api_status != 1:
            status = 'API_ERROR'
        else:
            # Vérification des métriques de qualité
            issues = []
            
            if ping is None:
                issues.append('ping_null')
            elif ping > config['max_acceptable_ping']:
                issues.append('ping_high')
            
            if servers < config['min_servers_expected']:
                issues.append('servers_low')
            
            if data_age_minutes > config['max_data_age_minutes']:
                issues.append('data_old')
            
            if not issues:
                status = 'UP'
            elif len(issues) == 1 and issues[0] not in ['ping_null', 'data_old']:
                status = 'DEGRADED'
            else:
                status = 'DOWN'
        
        analysis['status'] = status
        
        # Debug des issues pour comprendre pourquoi DOWN
        if issues:
            print(f"\n⚠️ Issues détectées: {issues}")
            for issue in issues:
                if issue == 'ping_high':
                    print(f"   🔴 Ping trop élevé: {ping}ms > {config['max_acceptable_ping']}ms")
                elif issue == 'servers_low':
                    print(f"   🔴 Peu de serveurs: {servers} < {config['min_servers_expected']}")
                elif issue == 'data_old':
                    print(f"   🔴 Données anciennes: {data_age_minutes:.1f}min > {config['max_data_age_minutes']}min")
                elif issue == 'ping_null':
                    print("   🔴 Ping non disponible")
        else:
            print("\n✅ Aucune issue détectée")
        
        print("✅ Analyse terminée!")
        print(f"📊 État final déterminé: {status}")
        
        # Détails de l'analyse
        print("\n📋 Analyse détaillée:")
        print(f"   🤖 API Status: {api_status} ({'UP' if api_status == 1 else 'DOWN' if api_status == 0 else 'UNKNOWN' if api_status == -1 else 'ERROR'})")
        
        if ping is not None:
            ping_emoji = "🟢" if ping <= 100 else "🟡" if ping <= 200 else "🔴"
            print(f"   {ping_emoji} Ping: {ping}ms")
        else:
            print("   ⚫ Ping: null")
        
        servers_emoji = "🟢" if servers >= 1200 else "🟡" if servers >= 1000 else "🔴"
        print(f"   {servers_emoji} Serveurs: {servers:,}")
        
        print(f"   👥 Joueurs: {players:,}")
        
        age_emoji = "🟢" if data_age_minutes <= 5 else "🟡" if data_age_minutes <= 10 else "🔴"
        print(f"   {age_emoji} Âge données: {data_age_minutes:.1f}min")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Erreur analyse: {e}")
        return None

def test_discord_embed_generation(analysis):
    """Teste la génération d'embed Discord."""
    print("\n🎨 Test génération embed Discord")
    print("=" * 35)
    
    if not analysis:
        print("❌ Pas d'analyse pour générer l'embed")
        return None
    
    try:
        status = analysis['status']
        
        # Configuration visuelle
        if status == 'UP':
            color = 0x00FF00
            emoji = "🟢"
            title = "🏎️ Serveurs ACC EN LIGNE"
        elif status == 'DEGRADED':
            color = 0xFFA500
            emoji = "🟡"  
            title = "🏎️ Serveurs ACC DÉGRADÉS"
        elif status == 'UNKNOWN':
            color = 0x808080
            emoji = "❓"
            title = "🏎️ Statut ACC INCONNU"
        else:
            color = 0xFF0000
            emoji = "🔴"
            title = "🏎️ Serveurs ACC HORS LIGNE"
        
        # Construction de l'embed
        embed = {
            "embeds": [{
                "title": f"{emoji} {title}",
                "color": color,
                "timestamp": datetime.now().isoformat(),
                "url": "https://acc-status.jonatan.net/",
                "fields": [
                    {
                        "name": "📊 État détecté",
                        "value": f"`{status}`",
                        "inline": True
                    },
                    {
                        "name": "🤖 API Status", 
                        "value": f"`{analysis['api_status']}`",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "ACC API Monitor • Test local",
                    # "icon_url": "https://cdn.cloudflare.steamstatic.com/steam/apps/805550/header.jpg"
                    'icon_url': 'https://sm.ign.com/ign_fr/cover/a/assetto-co/assetto-corsa-competizione_g2pf.jpg'
                }
            }]
        }
        
        # Ajout des métriques
        if analysis.get('ping_ms') is not None:
            embed["embeds"][0]["fields"].append({
                "name": "🏓 Ping",
                "value": f"`{analysis['ping_ms']}ms`",
                "inline": True
            })
        
        if analysis.get('servers_count') is not None:
            embed["embeds"][0]["fields"].append({
                "name": "🖥️ Serveurs",
                "value": f"`{analysis['servers_count']:,}`",
                "inline": True
            })
        
        print("✅ Embed Discord généré!")
        print(f"   📌 Titre: {embed['embeds'][0]['title']}")
        print(f"   🎨 Couleur: #{color:06X}")
        print(f"   📊 Champs: {len(embed['embeds'][0]['fields'])}")
        
        return embed
        
    except Exception as e:
        print(f"❌ Erreur génération embed: {e}")
        return None

def test_discord_notification(embed):
    """Teste l'envoi de notification Discord."""
    print("\n🔔 Test notification Discord")
    print("=" * 30)
    
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    if not webhook_url:
        print("❌ Variable DISCORD_WEBHOOK_URL non définie")
        print("💡 Pour tester: export DISCORD_WEBHOOK_URL='votre_webhook'")
        return False
    
    if not test_webhook_format(webhook_url):
        print("❌ Format webhook invalide")
        print("📝 Format attendu: https://discord.com/api/webhooks/ID/TOKEN")
        return False
    
    print(f"✅ Webhook configuré: {webhook_url[:50]}...")
    
    if not embed:
        print("❌ Pas d'embed à envoyer")
        return False
    
    try:
        print("📤 Envoi de la notification...")
        response = requests.post(
            webhook_url,
            json=embed,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 204:
            print("✅ Notification Discord envoyée!")
            print("📱 Vérifiez votre serveur Discord")
            return True
        else:
            print(f"❌ Erreur Discord: HTTP {response.status_code}")
            if response.text:
                print(f"📄 Réponse: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur envoi Discord: {e}")
        return False

def interactive_setup():
    """Configuration interactive complète."""
    print("🏎️ ACC API Monitor - Configuration locale")
    print("=" * 45)
    
    print("ℹ️ Ce test vérifie votre configuration ACC complète:")
    print("   📡 API acc-status.jonatan.net")
    print("   🧠 Logique d'analyse des données")
    print("   🎨 Génération d'embed Discord")
    print("   🔔 Envoi de notifications")
    
    # Test 1: API
    print("\n1️⃣ Test de l'API ACC...")
    api_data, api_ok = test_acc_api_direct()
    
    if not api_ok:
        print("\n❌ ARRÊT: Impossible d'accéder à l'API ACC")
        print("💡 Vérifiez votre connexion Internet")
        return False
    
    # Test 2: Analyse
    print("\n2️⃣ Test de l'analyse des données...")
    analysis = test_analysis_logic(api_data)
    
    if not analysis:
        print("\n❌ ARRÊT: Erreur dans l'analyse des données")
        return False
    
    # Test 3: Génération embed
    print("\n3️⃣ Test génération embed Discord...")
    embed = test_discord_embed_generation(analysis)
    
    if not embed:
        print("\n❌ ARRÊT: Erreur génération embed")
        return False
    
    # Test 4: Discord (optionnel)
    print("\n4️⃣ Configuration Discord...")
    webhook_url = input("URL de votre webhook Discord (ENTER pour ignorer): ").strip()
    
    discord_ok = False
    if webhook_url:
        os.environ['DISCORD_WEBHOOK_URL'] = webhook_url
        discord_ok = test_discord_notification(embed)
    else:
        print("⚠️ Test Discord ignoré")
    
    # Résumé final
    print("\n🎯 RÉSUMÉ DE LA CONFIGURATION")
    print("=" * 35)
    print(f"✅ Accès API ACC: OK")
    print(f"✅ Analyse données: OK")
    print(f"✅ Génération embed: OK")
    print(f"{'✅' if discord_ok else '⚠️'} Notifications Discord: {'OK' if discord_ok else 'Non testé'}")
    
    # État actuel des serveurs
    print(f"\n📊 État actuel des serveurs ACC:")
    print(f"   🤖 API: {analysis.get('api_status')} ({'UP' if analysis.get('api_status') == 1 else 'DOWN' if analysis.get('api_status') == 0 else 'UNKNOWN'})")
    print(f"   📊 État final: {analysis['status']}")
    
    if analysis.get('ping_ms') is not None:
        print(f"   🏓 Ping: {analysis['ping_ms']}ms")
    if analysis.get('servers_count') is not None:
        print(f"   🖥️ Serveurs: {analysis['servers_count']:,}")
    if analysis.get('players_count') is not None:
        print(f"   👥 Joueurs: {analysis['players_count']:,}")
    
    print("\n📋 Prochaines étapes:")
    print("1. Sauvegardez acc_api_monitor.py dans votre repo")
    print("2. Ajoutez le secret DISCORD_WEBHOOK_URL dans GitHub")
    print("3. Configurez le workflow GitHub Actions")
    print("4. Démarrez le monitoring automatique!")
    
    return True

def quick_test():
    """Test rapide avec configuration existante."""
    print("🚀 Test rapide ACC API")
    print("=" * 25)
    
    # Test API simple
    api_data, api_ok = test_acc_api_direct()
    
    if not api_ok:
        return False
    
    # Test analyse
    analysis = test_analysis_logic(api_data)
    
    if not analysis:
        return False
    
    print(f"\n✅ Test rapide terminé!")
    print(f"📊 État ACC détecté: {analysis['status']}")
    
    # Test Discord si configuré
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if webhook_url:
        print("\n🔔 Test notification Discord...")
        embed = test_discord_embed_generation(analysis)
        if embed:
            discord_ok = test_discord_notification(embed)
            if discord_ok:
                print("✅ Configuration complète fonctionnelle!")
            else:
                print("⚠️ Configuration API OK, Discord KO")
        
    return True

def show_api_example():
    """Affiche des exemples de données API."""
    print("📡 Exemples de données API ACC")
    print("=" * 35)
    
    example_up = {
        "status": 1,
        "ping": 35,
        "servers": 1600,
        "players": 850,
        "date": "2023-01-01T03:00:00.000Z"
    }
    
    example_down = {
        "status": 0,
        "ping": None,
        "servers": 1600,
        "players": 0,
        "date": "2023-01-01T03:00:00.000Z",
        "down_since": "2023-01-01T02:00:00.000Z"
    }
    
    print("✅ Exemple API - Serveurs UP:")
    print(json.dumps(example_up, indent=2))
    
    print("\n❌ Exemple API - Serveurs DOWN:")
    print(json.dumps(example_down, indent=2))
    
    print("\n📋 Signification des champs:")
    print("   status: 1=UP, 0=DOWN, -1=UNKNOWN")
    print("   ping: Latence en ms (null si DOWN)")
    print("   servers: Nombre de serveurs publics")
    print("   players: Joueurs connectés")
    print("   date: Timestamp de la vérification")

def main():
    """Fonction principale du test."""
    print("🧪 ACC API Monitor - Tests locaux")
    print("=" * 40)
    
    return interactive_setup()

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrompu par l'utilisateur")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Erreur inattendue: {e}")
        sys.exit(1)