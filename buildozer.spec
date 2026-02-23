[app]
title = SurveyMap SL
package.name = surveymapsl
package.domain = org.vithana
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 4.1
requirements = python3,kivy,ezdxf,jnius,android
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_catch_all = True

[buildozer]
log_level = 2
warn_on_root = 1
