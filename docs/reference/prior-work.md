# 参考：先行事例

偏光測定のアイディアに前例があるかを調べた結果。
調査日は2026年10月11日。数回のウェブ検索による調査であり、網羅的ではない。

## 1. 結論

- 原理と個々の要素には前例がある。
- 新しいと言えそうなのは、組み合わせと一部の工夫である。
- 位置づけは「原理が新しい」ではなく、「身近な機材で、全班が同時に、複数の試料を一度に測れる」とするのが正確である。

## 2. 前例があるもの

### 2.1 マリュスの法則をスマホで確かめる

| 事例 | 内容 |
|---|---|
| Monteiro ほか「The Polarization of Light and Malus' Law Using Smartphones」The Physics Teacher 55, 264 (2017) | パソコン画面を直線偏光の光源とし、スマホの照度センサーと姿勢センサーで、角度ごとの光の強さを測る。「回転角と明るさの同時記録」の骨格はこれと同じ。 https://arxiv.org/abs/1607.02659 |
| 動画解析によるマリュスの法則（下記レビューに掲載） | カメラの前で偏光板を回して撮影し、動画解析ソフトで明るさと角度を求める。 |
| phyphox フォーラムの実装例 | 照度センサーと加速度センサーから、明るさと回転角を同時に取る。 https://phyphox.org/forums/showthread.php?pid=2158 |
| Gallitto ほか「A Low-Cost Smartphone Polarimeter and Malus's Law」The Physics Teacher 62(8), 653–655 (2024) | 偏光フィルター2枚とスマホの照度センサーによる低価格の装置。 https://iris.unipa.it/handle/10447/661873 |

レビュー：「Mobile Devices and Sensors for Physics Teaching」 https://arxiv.org/pdf/2206.12062

### 2.2 旋光を身近な機材で測る

| 事例 | 内容 |
|---|---|
| Thomson「Is that a polarimeter in your pocket?」Journal of Chemical Education 95(5), 837–841 (2018) | 書画カメラ、スマホ画面（偏光光源）、3Dメガネ（偏光フィルター）、コンパスアプリで、液体の旋光角を測る。 https://strathprints.strath.ac.uk/id/eprint/63617 |
| Raspberry Pi による低価格の旋光計（学会発表） | 検光子を回して強度を記録し、試料による正弦曲線の位相のずれから旋光角を求める。 https://conference.pixel-online.net/files/npse/ed0010/FP/4390-CHEM4956-FP-NPSE10.pdf |
| Vernier「Go Direct Polarimeter」（製品） | 縦型。検光子をモーターで自動回転し、グラフを表示する。589 nm の LED、精度 ±1°、559ドル。 https://turbo.vernier.com/gdx-pol/ |

### 2.3 色ごとの旋光（旋光分散）

| 事例 | 内容 |
|---|---|
| 福岡教育大学の報告 | 白色光と RGB カラーセンサーで、ショ糖の赤・緑・青それぞれの比旋光度を求める学生実験用の装置。 https://fukuoka-edu.repo.nii.ac.jp/record/76/files/Utoh_kyushu_6_2.pdf |
| 「A visual understanding of optical rotation using corn syrup」 | カメラで旋光を撮影して定量化し、旋光分散への拡張に触れている。 https://durham-repository.worktribe.com/OutputFile/1356419 |
| 自作旋光計による3波長での糖の測定（Journal of Chemical Education、2025年） | 市販部品で組んだ旋光計を使う学生実験。 https://research.tec.mx/vivo-tec/display/AcademicArticleSCO_85213269571 |

## 3. 今回の調査では見つからなかったもの

- ブランクと複数の試料を1枚の画像に写して同時に測ること
- リサージュ図形で、角度を測らずに位相差を読むこと
- 画像内の非偏光の基準領域で、自動露出を打ち消すこと
- 安価な電動回転台で光源側を回すこと
- これらをインストール不要のブラウザアプリにまとめること

見つからなかっただけで、存在しないとは言えない。新規性を主張する場面では、さらに調査が要る（POL-Q-20）。

## 4. 設計への示唆

- 位相のずれから旋光角を求める方法には実績がある。測定原理は成立する見込みが高い。
- 市販品の精度が ±1° である。本アプリの当面の見込みは ±2° 程度とする（POL-N-03）。
- パソコン画面を光源にした事例が多い。スマホ画面は機種によって偏光の種類が違うので、光源側にも偏光フィルムを貼る（`02-apparatus.md` の1節）。
