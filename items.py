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
    '/tmp/fixed-ghostscript.deb': {
        'url': 'https://github.com/paperless-ngx/builder/releases/download/ghostscript-10.03.1/ghostscript_10.03.1.dfsg-1_amd64.deb',
        'sha512': '6dded58246d834f7b6033b3a8637d58105ae1404a180598ea11ac9101caf33709b2f2f7444fc38bb57222c127c25a748afc39f03631a422b89022be9a8b50d38',
    },
    '/tmp/fixed-libgs-common.deb': {
        'url': 'https://github.com/paperless-ngx/builder/releases/download/ghostscript-10.03.1/libgs-common_10.03.1.dfsg-1_all.deb',
        'sha512': 'a7606311a4d5916aa17203076dd8a358cedea6128fc669ae40014876f4ffbb47403d72de82ec525d58b4af61db9233ea40f40dac4d213009c0a065147ef1bd97',
    },
    '/tmp/fixed-libgs10-common.deb': {
        'url': 'https://github.com/paperless-ngx/builder/releases/download/ghostscript-10.03.1/libgs10-common_10.03.1.dfsg-1_all.deb',
        'sha512': '57e4f32bb77bf6c36ee04d4154ea29691f694fa04461cb9d2ccc3666fb34882b5471bb5ccd830f6972be420beaf845fbdb74d757656a4477d8a559e86ce622d2',
    },
    '/tmp/fixed-libgs10.deb': {
        'url': 'https://github.com/paperless-ngx/builder/releases/download/ghostscript-10.03.1/libgs10_10.03.1.dfsg-1_amd64.deb',
        'sha512': '427ab4ee492eaa7f15d05e671bb96979c9fa6f14bed7d7f47a4c1aeb8d78eb39e58221610555ef568a0f48213dcac1fc7f006c625b9728a06292b6fdd2174e57',
    }
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
    },
    'install_fixed_paperless_ghostscript': {
        'command': 'dpkg -i /tmp/fixed-libgs-common.deb /tmp/fixed-libgs10-common.deb /tmp/fixed-libgs10.deb /tmp/fixed-ghostscript.deb',
        'needs': [
            'pkg_apt:',
            'downloads:',
        ],
    },
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
