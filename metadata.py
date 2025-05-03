import os.path
import urllib.parse

import hashlib
import urllib

defaults = {
    'paperless': {
        'url': 'https://example.org',
        'version': '2.15.3',
        'checksum_sha512': 'c22131b42b0147516a08ae33991ac13e1e6771e35b997d4213b8094fc74146bd351c93a30fa66c4f46514312cbe8314f2c7c4ccdee33b71853a897f5ddbfaa04',
        'basedir': '/opt/paperless',
        'redis': 'redis://localhost:6379',
        'db': {
            'host': 'localhost',
            'port': 5432,
            'name': 'paperless',
            'user': 'paperless',
            'password': repo.vault.password_for(f'postgres_paperless_{node.name}').value,
            'ssl_mode': 'prefer',
        },
        'env': {
            #'PAPERLESS_DATA_DIR': '../data/'
            #'PAPERLESS_CONSUMER_RECURSIVE': True,
            #'PAPERLESS_CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED': True,
        },
        'secret_key': repo.vault.password_for(f'paperless_secret_key_{node.name}').value,
        'disable_postgres_integration': False,
        'dsiable_redis_integration': False,
        'disable_nginx_integration': False,
    },
}

if node.has_bundle('apt'):
    defaults['apt'] = {
        'packages': {
            'python3': {},
            'python3-venv': {},
            'python3-pip': {},
            'python3-dev': {},
            'imagemagick': {},
            'fonts-liberation': {},
            'gnupg': {},
            'libpq-dev': {},
            'default-libmysqlclient-dev': {},
            'pkg-config': {},
            'libmagic-dev': {},
            'libzbar0': {},
            'poppler-utils': {},
            'unpaper': {},
            'ghostscript': {},
            'icc-profiles-free': {},
            'qpdf': {},
            'liblept5': {},
            'libxml2': {},
            'pngquant': {},
            'zlib1g': {},
            'tesseract-ocr': {},
            'build-essential': {},
            'python3-wheel': {},
            'python3-setuptools': {},
        },
    }


@metadata_reactor
def paperless_postgres_integration(metadata):
    if not node.has_bundle('postgres') or metadata.get('paperless/disable_postgres_integration', False):
        raise DoNotRunAgain

    return {
        'postgres': {
            'roles': {
                'paperless': {
                    'password': repo.vault.password_for(f'postgres_paperless_{node.name}').value,
                },
            },
            'databases': {
                'paperless': {
                    'owner_name': 'paperless',
                    'owner_password': repo.vault.password_for(f'postgres_paperless_{node.name}').value,
                },
            },
        },
    }

@metadata_reactor
def paperless_redis_integration(metadata):
    if not node.has_bundle('redis') or metadata.get('paperless/disable_redis_integration', False):
        raise DoNotRunAgain


    def get_random_port(name:str) -> int:
        return 6380 + (int(hashlib.sha256(name.encode('utf-8')).hexdigest(), 16) % (6400 - 6380 + 1))

    # We already have multiple servers, so lets create another one
    if len(metadata.get('redis/servers', {})) > 1:
        redis_port = get_random_port(f'redis_port_{node.name}')
        return {
            'paperless': {
                'redis': f'redis://localhost:{redis_port}',
            },
            'redis': {
                'servers': {
                    'paperless': {
                        'port': get_random_port(f'redis_port_{node.name}')
                    },
                },
            }
        }

    port = 6379
    if len(metadata.get('redis/servers', {})) == 1:
        port = metadata.get('redis/servers').get('port', 6379)
    return {
        'paperless': {
            'redis': f'redis://localhost:{port}',
        },
    }

@metadata_reactor
def paperless_nginx_integration(metadata):
    if not node.has_bundle('nginx') or metadata.get('paperless/disable_nginx_integration', False):
        raise DoNotRunAgain

    url = urllib.parse.urlparse(metadata.get('paperless/url'))
    return {
        'nginx': {
            'sites': {
                url.hostname: {
                    'enabled': True,
                    'ssl': {
                        'letsencrypt': url.scheme == 'https',
                    },
                },
                'location': {
                    '/': [
                        # These configuration options are required for WebSockets to work.
                        'proxy_http_version 1.1;',
                        'proxy_set_header Upgrade $http_upgrade;',
                        'proxy_set_header Connection "upgrade";',

                        'proxy_redirect off;',
                        'proxy_set_header Host $host:$server_port;',
                        'proxy_set_header X-Real-IP $remote_addr;',
                        'proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;',
                        'proxy_set_header X-Forwarded-Host $server_name;',
                        'proxy_set_header X-Forwarded-Proto $scheme;',
                        'add_header Referrer-Policy "strict-origin-when-cross-origin";',
                    ],
                },
            },
        },
    }

@metadata_reactor
def paperless_restic_integration(metadata):
    if not node.has_bundle('restic'):
        raise DoNotRunAgain

    src_dir = os.path.join(metadata.get('paperless/basedir'), 'src')
    data_dir = os.path.normpath(os.path.join(src_dir, metadata.get('paperless/env').get('PAPERLESS_DATA_DIR', '../data/')))
    media_dir = os.path.normpath(os.path.join(src_dir, metadata.get('paperless/env').get('PAPERLESS_DATA_DIR', '../media/')))

    return {
        'restic': {
            'backup_folders': [
                data_dir,
                media_dir,
            ],
        }
    }
