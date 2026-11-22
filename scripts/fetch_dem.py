# -*- coding: utf-8 -*-
"""国土地理院の標高タイル（DEM10B 由来の dem タイル、テキスト形式）を取得する。

使い方（Blender ではなく通常の Python 3 で実行）:
    python scripts/fetch_dem.py [出力ディレクトリ]

既定の出力先は <リポジトリ>/output/dem（HEIAN_WORK があれば <HEIAN_WORK>/dem）。
取得済みのタイルは飛ばすので、何度実行してもよい。

範囲は京都盆地とその周りの山（東山・北山・西山）を含む
東経135.58〜135.90°・北緯34.86〜35.16°（約29km×33km）、ズーム12（約30m間隔）。
タイル1枚は256×256の標高値（m）をカンマ区切りで並べたもので、
海や欠測は "e" になっている。

出典：国土地理院 標高タイル（https://maps.gsi.go.jp/development/ichiran.html）。
利用は国土地理院コンテンツ利用規約に従い、成果物には出典を明記する。
環境レイヤーでは**山の形だけ**を借り、平地（盆地の床）は使わない
（現代の造成地形を平安京に持ち込まないため。build_environment.py 参照）。
"""
import math
import os
import sys
import time
import urllib.request

Z = 12
LON_MIN, LON_MAX = 135.58, 135.90
LAT_MIN, LAT_MAX = 34.86, 35.16
URL = "https://cyberjapandata.gsi.go.jp/xyz/dem/{z}/{x}/{y}.txt"


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lr = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lr) + 1.0 / math.cos(lr)) / math.pi) / 2.0 * n)
    return x, y


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work = os.environ.get("HEIAN_WORK", os.path.join(repo, "output"))
    out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(work, "dem")
    os.makedirs(out, exist_ok=True)
    x0, y0 = tile_xy(LON_MIN, LAT_MAX, Z)
    x1, y1 = tile_xy(LON_MAX, LAT_MIN, Z)
    total = 0
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            path = os.path.join(out, "dem_%d_%d_%d.txt" % (Z, tx, ty))
            if os.path.exists(path) and os.path.getsize(path) > 0:
                total += os.path.getsize(path)
                continue
            req = urllib.request.Request(URL.format(z=Z, x=tx, y=ty),
                                         headers={"User-Agent": "heian-blender-dem-fetch"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            with open(path, "wb") as f:
                f.write(data)
            total += len(data)
            print("GOT", os.path.basename(path), len(data), flush=True)
            time.sleep(0.3)  # 配信側への負荷を避ける
    print("DEM_DONE tiles=%d x=%d..%d y=%d..%d bytes=%d dir=%s"
          % ((x1 - x0 + 1) * (y1 - y0 + 1), x0, x1, y0, y1, total, out))


if __name__ == "__main__":
    main()
