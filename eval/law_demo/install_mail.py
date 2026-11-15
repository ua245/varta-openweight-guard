from pathlib import Path
import json,secrets,subprocess
root=Path.home()/'varta-evaluation-20261115/law-demo-runtime';root.mkdir(exist_ok=True)
account=root/'mail-account.json'
if not account.exists():
 account.write_text(json.dumps({'username':'associate@kingsbridge.test','password':secrets.token_urlsafe(20),'imap_host':'127.0.0.1','imap_port':1144,'smtp_host':'127.0.0.1','smtp_port':2526},indent=2)+'\n');account.chmod(0o600)
a=json.loads(account.read_text())
compose=f'''services:
  mail:
    image: greenmail/standalone:2.1.15
    container_name: varta-law-mail
    restart: unless-stopped
    mem_limit: 256m
    environment:
      JAVA_TOOL_OPTIONS: -Xms32m -Xmx128m
      GREENMAIL_OPTS: -Dgreenmail.setup.test.smtp -Dgreenmail.setup.test.imap -Dgreenmail.hostname=0.0.0.0 -Dgreenmail.users=associate:{a['password']}@kingsbridge.test -Dgreenmail.users.login=email
    ports:
      - 127.0.0.1:2526:3025
      - 127.0.0.1:1144:3143
  roundcube:
    image: roundcube/roundcubemail:latest
    container_name: varta-law-roundcube
    restart: unless-stopped
    mem_limit: 256m
    depends_on: [mail]
    environment:
      ROUNDCUBEMAIL_DEFAULT_HOST: mail
      ROUNDCUBEMAIL_DEFAULT_PORT: 3143
      ROUNDCUBEMAIL_SMTP_SERVER: mail
      ROUNDCUBEMAIL_SMTP_PORT: 3025
      ROUNDCUBEMAIL_DB_TYPE: sqlite
      ROUNDCUBEMAIL_SKIN: elastic
    ports:
      - 127.0.0.1:8096:80
    volumes:
      - roundcube_db:/var/roundcube/db
      - ./law-config.php:/var/roundcube/config/law-config.php:ro
volumes:
  roundcube_db:
'''
(root/'compose.yaml').write_text(compose);(root/'compose.yaml').chmod(0o600)
(root/'law-config.php').write_text("<?php\n$config['product_name'] = 'Kingsbridge Vale LLP | Matter Mail';\n$config['support_url'] = '';\n$config['smtp_user'] = '%u';\n$config['smtp_pass'] = '%p';\n$config['spellcheck_engine'] = 'pspell';\n")
subprocess.run(['docker','compose','-p','varta-law','-f',str(root/'compose.yaml'),'up','-d'],check=True)
print('Roundcube demo mail requested on loopback8096; account in private runtimefile.')
