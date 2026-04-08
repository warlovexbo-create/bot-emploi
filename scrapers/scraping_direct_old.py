import requests
from bs4 import BeautifulSoup
import time
import random
from urllib.parse import quote

def chercher_toutes(ville, rayon_km):
    """Interface standard pour main.py - retourne liste d'offres dict"""
    toutes_offres = []
    
    # Indeed (headers anti-detection 2026)
    print("  [IN] Scraping Indeed France...")
    toutes_offres.extend(scrape_indeed(ville))
    
    # HelloWork
    print("  [HW] Scraping HelloWork...")
    toutes_offres.extend(scrape_helloworld(ville))
    
    # Déduplication
    uniques = []
    ids_vus = set()
    for offre in toutes_offres:
        offre_id = offre.get('id', offre.get('url', ''))  # Dédoublonnage par ID
        if offre_id not in ids_vus:
            uniques.append(offre)
            ids_vus.add(offre_id)
    
    print(f"  [SCRAPING] ✓ {len(uniques)} offres uniques Indeed + HelloWork")
    return uniques

def scrape_indeed(ville):
    offres = []
    mots_cles = [
        f"alternance+immobilier+{ville.lower()}",
        f"alternance+BTS+immobilier+{ville.lower()}",
        f"apprentissage+immobilier+{ville.lower()}",
        f"alternance+négociateur+immobilier+{ville.lower()}"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'sec-ch-ua': '"Google Chrome";v="123", "Chromium";v="123", "Not:A-Brand";v="8"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }
    
    for mot_cle in mots_cles:
        try:
            url = f"https://fr.indeed.com/jobs?q={mot_cle}&l={ville}"
            print(f"    [IN] '{mot_cle}'...")
            
            session = requests.Session()
            session.headers.update(headers)
            time.sleep(random.uniform(2, 5))  # Pause anti-bot
            
            response = session.get(url, timeout=10)
            
            if response.status_code == 403:
                print(f"    [IN] ✗ 403 → 0 résultats")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            jobs = soup.find_all('div', class_='job_seen_beacon')
            
            for job in jobs[:3]:  # Max 3 par requête
                titre = job.find('h2')
                entreprise = job.find('span', class_='companyName')
                lien = job.find('a', href=True)
                
                if titre and lien:
                    titre_txt = titre.get_text(strip=True)
                    entrep_txt = entreprise.get_text(strip=True) if entreprise else 'N/A'
                    offre = {
                        'id': 'in_' + lien['href'][-12:].replace('/', ''),
                        'titre': titre_txt,
                        'entreprise': entrep_txt,
                        'ville': ville,
                        'url': f"https://fr.indeed.com{lien['href']}",
                        'salaire': '',
                        'description': titre_txt + ' ' + entrep_txt,
                        'source': 'Indeed',
                        'contrat': 'Alternance',
                        'score': 0,
                    }
                    offres.append(offre)
            
            print(f"    [IN] ✓ {len(jobs)} résultats")
            break  # Une requête suffit
            
        except Exception as e:
            print(f"    [IN] ✗ Erreur: {e}")
            continue
    
    print(f"[IN] ✓ {len(offres)} offres uniques Indeed")
    return offres

def scrape_helloworld(ville):
    offres = []
    mots_cles = [
        'alternance-immobilier',
        'alternance-bts-immobilier',
        'apprentissage-immobilier',
        'alternance-negociateur-immobilier'
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    for mot_cle in mots_cles:
        try:
            url = f"https://www.hellowork.com/fr-fr/emploi/{mot_cle}_{ville.lower()}.html"
            print(f"      [HW] '{mot_cle}'...")
            
            time.sleep(random.uniform(1, 3))
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 403:
                print("       → 0 résultats (403)")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            jobs = soup.find_all('div', class_='offer-card')
            
            for job in jobs[:3]:
                titre = job.find('h3')
                entreprise = job.find('span', class_='company-name')
                lien = job.find('a', href=True)
                
                if titre and lien:
                    titre_txt = titre.get_text(strip=True)
                    entrep_txt = entreprise.get_text(strip=True) if entreprise else 'N/A'
                    offre = {
                        'id': 'hw_' + lien['href'][-12:].replace('/', ''),
                        'titre': titre_txt,
                        'entreprise': entrep_txt,
                        'ville': ville,
                        'url': f"https://www.hellowork.com{lien['href']}",
                        'salaire': '',
                        'description': titre_txt + ' ' + entrep_txt,
                        'source': 'HelloWork',
                        'contrat': 'Alternance',
                        'score': 0,
                    }
                    offres.append(offre)
            
            print(f"       → {len(jobs)} résultats")
            break
            
        except Exception as e:
            print(f"       → 0 résultats (erreur)")
            continue
    
    print(f"[HW] ✓ {len(offres)} offres uniques HelloWork")
    return offres

if __name__ == "__main__":
    print("[TEST] Scraping direct Indeed + HelloWork")
    offres = chercher_toutes("Toulouse", 20)
    print(f"TOTAL: {len(offres)} offres")