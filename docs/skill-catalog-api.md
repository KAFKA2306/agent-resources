# スキル・カタログAPI

`agent-resources` の正準 `skills/` ディレクトリを、依存関係なしで参照できる静的JSONとして配布します。

## エンドポイント

GitHub Pagesへの反映後は次のURLで取得できます。

- `https://kafka2306.github.io/agent-resources/api/v1/skill-collections.json`
- `https://kafka2306.github.io/agent-resources/api/v1/manifest.json`

リポジトリから直接取得する場合:

```bash
curl -fsSLO https://raw.githubusercontent.com/KAFKA2306/agent-resources/main/api/v1/skill-collections.json
curl -fsSLO https://raw.githubusercontent.com/KAFKA2306/agent-resources/main/api/v1/manifest.json
```

## データ辞書

| フィールド | 型 | 意味 |
| --- | --- | --- |
| `schema` | string | 後方互換性を判定するスキーマ識別子 |
| `generated_at` | ISO 8601 string | GitHub公式Contents APIを確認した日時 |
| `source.ref` | string | 取得対象のGit ref |
| `count` | integer | `collections`の件数 |
| `collections[].id` | string | 安定したコレクション識別子 |
| `collections[].path` | string | リポジトリ内の正準パス |
| `collections[].tree_sha` | string | 取得時点のGit tree SHA |
| `collections[].kind` | `skill` / `collection` | 単一スキルか下位スキル群か |
| `collections[].source_url` | URL | 人間が内容を確認するための正準URL |

`tree_sha`が変わった場合、そのコレクション配下の内容が更新されています。クライアントは差分取得やローカルキャッシュ更新の判定に利用できます。

## 検索例

```bash
jq '.collections[] | select(.kind == "collection") | {id, path, tree_sha}' \
  api/v1/skill-collections.json
```

Python:

```python
import json
from urllib.request import urlopen

url = "https://kafka2306.github.io/agent-resources/api/v1/skill-collections.json"
with urlopen(url, timeout=10) as response:
    catalog = json.load(response)

writing = next(item for item in catalog["collections"] if item["id"] == "writing")
print(writing["source_url"])
```

## キャッシュと整合性

`manifest.json`には配布JSONのSHA-256と件数が入っています。ローカルキャッシュを置き換える前に、ダウンロードしたバイト列のSHA-256を照合してください。推奨キャッシュ時間は1時間です。

## 更新方針

- 既存のIDは名称変更時も可能な限り維持します。
- 破壊的変更は新しいAPIバージョンとスキーマ識別子で公開します。
- 出典はGitHub公式Contents API、データ本体のライセンスはリポジトリのMIT Licenseです。
- `skills/`を変更するPRでは、カタログ、manifest、テストを同時に更新します。
