# -*- coding: utf-8 -*-
"""gh_release.py - publish the APK to a GitHub Release.

Reads the token from the GH_TOKEN environment variable so it never appears
in argv or in a shell history file.

Usage:
    python gh_release.py check
    python gh_release.py publish <apk_path> <tag> <release_name>
"""
import os
import sys
import json
import mimetypes

import requests

OWNER = 'newliver666'
REPO = 'bilinovel-rm'
API = 'https://api.github.com'
PROXY = {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}


def token():
    t = os.environ.get('GH_TOKEN', '').strip()
    if not t:
        sys.exit('FAIL: GH_TOKEN env var is empty')
    return t


def headers():
    return {
        'Authorization': 'Bearer %s' % token(),
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'bilinovel-rm-release',
    }


def check():
    r = requests.get(API + '/user', headers=headers(), proxies=PROXY, timeout=40)
    print('GET /user ->', r.status_code)
    if r.status_code == 200:
        d = r.json()
        print('  login :', d.get('login'))
        print('  scopes:', r.headers.get('x-oauth-scopes'))
    else:
        print('  body:', r.text[:300])

    r = requests.get('%s/repos/%s/%s' % (API, OWNER, REPO),
                     headers=headers(), proxies=PROXY, timeout=40)
    print('GET /repos/%s/%s -> %s' % (OWNER, REPO, r.status_code))
    if r.status_code == 200:
        d = r.json()
        print('  full_name  :', d.get('full_name'))
        print('  private    :', d.get('private'))
        print('  default    :', d.get('default_branch'))
        print('  permissions:', d.get('permissions'))
    else:
        print('  body:', r.text[:300])
    return r.status_code == 200


def publish(apk, tag, name):
    size = os.path.getsize(apk)
    print('APK  : %s (%d bytes)' % (apk, size))

    # Reuse an existing release for the same tag instead of erroring out.
    url = '%s/repos/%s/%s/releases/tags/%s' % (API, OWNER, REPO, tag)
    r = requests.get(url, headers=headers(), proxies=PROXY, timeout=40)
    if r.status_code == 200:
        rel = r.json()
        print('release exists, id=%s' % rel['id'])
        # Drop any previously uploaded asset with the same name so we can
        # re-upload cleanly after a rebuild.
        for a in rel.get('assets', []):
            if a['name'] == os.path.basename(apk):
                dr = requests.delete(a['url'], headers=headers(),
                                     proxies=PROXY, timeout=40)
                print('deleted old asset %s -> %s' % (a['name'], dr.status_code))
    else:
        body = {
            'tag_name': tag,
            'name': name,
            'body': ('哔哩轻小说 Android 客户端 · 无广告版本\n\n'
                     '- 应用名称：哔哩轻小说\n'
                     '- 包名：com.linovelib.bilinovel\n'
                     '- 版本：%s\n'
                     '- 支持系统：Android 8.1 (API 27) 及以上\n'
                     '- 架构：通用（arm64-v8a / armeabi-v7a / x86_64）\n\n'
                     '移除了开屏广告与阅读页横幅广告，其余功能与原版一致。\n\n'
                     '**安装说明**\n\n'
                     '1. 下载下方 APK 文件到手机\n'
                     '2. 直接打开安装，允许「未知来源应用」\n'
                     '3. 如已安装官方版，需先卸载再安装（签名不同，无法覆盖）\n\n'
                     '详细说明见仓库 README。' % tag.lstrip('v')),
            'draft': False,
            'prerelease': False,
        }
        r = requests.post('%s/repos/%s/%s/releases' % (API, OWNER, REPO),
                          headers=headers(), json=body, proxies=PROXY, timeout=60)
        print('POST /releases ->', r.status_code)
        if r.status_code not in (200, 201):
            sys.exit('FAIL creating release: %s' % r.text[:500])
        rel = r.json()
        print('release created, id=%s' % rel['id'])

    # Upload the asset. The upload host differs from api.github.com, so we
    # take it from the release payload.
    up = rel['upload_url'].split('{')[0]
    fname = os.path.basename(apk)
    ctype = mimetypes.guess_type(fname)[0] or 'application/vnd.android.package-archive'
    h = headers()
    h['Content-Type'] = ctype
    with open(apk, 'rb') as f:
        data = f.read()
    print('uploading %s (%d bytes, %s) ...' % (fname, len(data), ctype))
    r = requests.post('%s?name=%s' % (up, fname), headers=h, data=data,
                      proxies=PROXY, timeout=1800)
    print('POST upload ->', r.status_code)
    if r.status_code not in (200, 201):
        sys.exit('FAIL uploading asset: %s' % r.text[:500])
    a = r.json()
    print('  asset name :', a['name'])
    print('  asset size :', a['size'])
    print('  state      :', a['state'])
    print('  download   :', a['browser_download_url'])
    print('\nRELEASE URL: %s' % rel['html_url'])


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'check':
        check()
    elif cmd == 'publish':
        publish(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        sys.exit(__doc__)
