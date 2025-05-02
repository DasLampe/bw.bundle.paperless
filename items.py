global node

cfg = node.metadata.get('paperless', {})
venv_path = f'{cfg.get('basedir')}/.venv'

files ={
    f'{cfg.get("basedir")}/get_version.py': {
        'source': 'get_version.py.j2',
        'content_type': 'jinja2',
        'context': {
            'basedir': cfg.get('basedir'),
        },
        'owner': 'paperless',
        'group': 'paperless',
        'needs': [
            f'directory:{cfg.get("basedir")}',
        ]
    },
    f'{cfg.get("basedir")}/paperless.conf': {
        'source': 'paperless.conf.j2',
        'content_type': 'jinja2',
        'context': {
            'basedir': cfg.get('basedir'),
            'redis': cfg.get('redis'),
            'db': cfg.get('db'),
            'cfg': cfg,
        },
        'owner': 'paperless',
        'group': 'paperless',
        'needs': [
            'action:unpack_paperless',
        ],
    }
}
svc_systemd = {}

users = {
    'paperless': {
        'home': cfg.get('basedir'),
    },
}

downloads = {
    f'/tmp/paperless-{cfg.get('version')}.tar.xz': {
        'url': f'https://github.com/paperless-ngx/paperless-ngx/releases/download/v{cfg.get('version')}/paperless-ngx-v{cfg.get('version')}.tar.xz',
        'sha512': cfg.get('checksum_sha512'),
    },
}

actions = {
    'create_paperless_venv': {
        'command': f'sudo -Hu paperless python3 -m venv {venv_path}',
        'unless': f'test -d {venv_path}',
        'needs': [
            'user:paperless',
            'pkg_apt:python3-venv',
            f'directory:{cfg.get("basedir")}',
        ],
    },
    'unpack_paperless': {
        'command': f'tar -xf /tmp/paperless-{cfg.get('version')}.tar.xz -C {cfg.get('basedir')}/ --strip-components=1',
        'unless': f'PAPERLESS_VERSION={cfg.get('version')} python3 {cfg.get("basedir")}/get_version.py',
        'needs': [
            f'file:{cfg.get("basedir")}/get_version.py',
            'action:create_paperless_venv',
            f'download:/tmp/paperless-{cfg.get('version')}.tar.xz',
            f'directory:{cfg.get("basedir")}',
            'pkg_apt:',
        ],
        'triggers': [
            'action:paperless_pip_install',
        ]
    },
    'paperless_pip_install': {
        'command': f'cd {cfg.get("basedir")} && sudo -Hu paperless {venv_path}/bin/pip3 install -r {cfg.get('basedir')}/requirements.txt',
        'needs': [
            'tag:paperless_directories',
            f'file:{cfg.get("basedir")}/paperless.conf',
        ],
        'triggers': [
            'action:paperless_db_migration',
        ],
        'triggered': True,
    },
    'paperless_db_migration': {
        'command': f'cd {cfg.get('basedir')}/src && sudo -Hu paperless {venv_path}/bin/python3 manage.py migrate',
        'needs': [
            'action:paperless_pip_install',
        ],
        'triggered': True,
    },
    'paperless_daemon_reload': {
        'command': 'systemctl daemon-reload',
        'triggered': True,
    }
}

directories = {
    cfg.get('basedir'): {
        'owner': 'paperless',
        'group': 'paperless',
    },
}

# Create directories
for d in ["data", "media", "consume"]:
    directories[f'{cfg.get('basedir')}/{d}'] = {
        'owner': 'paperless',
        'group': 'paperless',
        'tags': [
            'paperless_directories',
        ]
    }

# Create and enable systemd units
for u in ["consumer", "scheduler", "task-queue", "webserver"]:
    files[f'/etc/systemd/system/paperless-{u}.service'] = {
        'source': f'etc/systemd/system/paperless-{u}.service.j2',
        'content_type': 'jinja2',
        'context': {
            'basedir': cfg.get('basedir'),
        },
        'triggers': [
            'action:paperless_daemon_reload',
        ],
        'after': [
            'action:paperless_db_migration',
        ],
    }
    svc_systemd[f'paperless-{u}.service'] = {
        'enabled': True,
        'running': True,
        'needs': [
            f'file:/etc/systemd/system/paperless-{u}.service',
        ],
    }
