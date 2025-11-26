
[app]
title = FishByte
package.name = fishbyte
package.domain = org.fishbyte
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0
requirements = python3,kivy==2.2.0,kivymd,pillow,requests,urllib3,chardet,idna,certifi,openssl,ephem,materialyoucolor,exceptiongroup,asyncgui
orientation = portrait
osx.python_version = 3
osx.kivy_version = 1.9.1
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 21
android.sdk = 24
android.ndk = 25b
android.ndk_api = 21
android.private_storage = True
android.accept_sdk_license = True
android.entrypoint = org.kivy.android.PythonActivity
android.activity_class_name = org.kivy.android.PythonActivity
android.service_class_name = org.kivy.android.PythonService
android.allow_backup = True
android.archs = arm64-v8a
p4a.branch = master
[buildozer]
log_level = 2

warn_on_root = 1
