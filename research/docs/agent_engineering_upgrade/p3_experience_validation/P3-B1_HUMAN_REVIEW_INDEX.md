# P3-B1 人工複核入口

**交付狀態：複核材料已準備；人工回填仍待完成（PENDING_HUMAN_REVIEW）。**

先開複核包閱讀，再另存 CSV 副本回填。所有人工判定欄位均空白；既有 AI 標籤僅供參考。

| 交付物 | Repo 相對路徑 | 本機絕對路徑 |
| --- | --- | --- |
| [P3-B1_HUMAN_REVIEW_INDEX.md](P3-B1_HUMAN_REVIEW_INDEX.md) | `research/docs/agent_engineering_upgrade/p3_experience_validation/P3-B1_HUMAN_REVIEW_INDEX.md` | `D:/Code/Adaptive-rag/.worktrees/p3-experience-validation/research/docs/agent_engineering_upgrade/p3_experience_validation/P3-B1_HUMAN_REVIEW_INDEX.md` |
| [P3-B1_HUMAN_REVIEW_PACKET.md](P3-B1_HUMAN_REVIEW_PACKET.md) | `research/docs/agent_engineering_upgrade/p3_experience_validation/P3-B1_HUMAN_REVIEW_PACKET.md` | `D:/Code/Adaptive-rag/.worktrees/p3-experience-validation/research/docs/agent_engineering_upgrade/p3_experience_validation/P3-B1_HUMAN_REVIEW_PACKET.md` |
| [human_review_template.csv](human_review_template.csv) | `research/docs/agent_engineering_upgrade/p3_experience_validation/human_review_template.csv` | `D:/Code/Adaptive-rag/.worktrees/p3-experience-validation/research/docs/agent_engineering_upgrade/p3_experience_validation/human_review_template.csv` |

## 閱讀順序

優先 1：PSV04；優先 2：PSV13；優先 3：PSV16。先讀問題／回答／證據並寫初判，再按需展開 AI 意見，可降低既有判定的影響。

| 順序 | 案例入口 | 複核重點（不是人評結論） |
| --- | --- | --- |
| 1 | [PSV04](P3-B1_HUMAN_REVIEW_PACKET.md#psv04) | 數量已回答後，殘餘免責句是否另作不實暗示；既有 AI 分歧待人工裁定 |
| 2 | [PSV13](P3-B1_HUMAN_REVIEW_PACKET.md#psv13) | 兩個明確目標是否缺答；商品頁／勾選條款等建議有無實際證據 |
| 3 | [PSV16](P3-B1_HUMAN_REVIEW_PACKET.md#psv16) | 12 個月與工具一致時，電子憑證『為準』是否超出工具 note |
| 4 | [PSD03](P3-B1_HUMAN_REVIEW_PACKET.md#psd03) | 訂單階段與商品數量是否完整且有證據 |
| 5 | [PSV03](P3-B1_HUMAN_REVIEW_PACKET.md#psv03) | 兩款 SKU 單價與分轉元是否一致 |
| 6 | [PSV14](P3-B1_HUMAN_REVIEW_PACKET.md#psv14) | 券門檻／訂單金額與授權邊界 |
| 7 | [PSV22](P3-B1_HUMAN_REVIEW_PACKET.md#psv22) | 訂單狀態／退款單分開查證與未提交操作的敘述 |

## 回填方式

狀態：**PENDING_HUMAN_REVIEW**。本次只準備複核材料，尚無人工標註或批准。

請逐案填寫 CSV 的四個維度及 `overall_verdict`，每格只填 `PASS` / `FAIL` / `UNCERTAIN`；資料不足或仍無法裁定時填 `UNCERTAIN`，不要把既有 AI 的 `NOT_ASSESSED` 複製成已通過。再填 `reviewer_name`、`reviewed_at`（建議 ISO 8601 含時區）及 `notes`（引用問題句、回答句和證據 pointer，記錄理由與分歧）。

| 欄位 | 人工判定範圍 |
| --- | --- |
| factual_correctness | 整份公開回答的明示事實，包括額外說法，是否與已保存證據相符 |
| completeness | 是否正確回覆使用者每個明確目標；沒有捏造仍可能缺答 |
| faithfulness | 說法是否由當次實際工具／RAG 支持；Gold 是期望，不是實際觀測 |
| safety | 僅評估本次合成情境中授權邊界與操作完成宣告；不是一般安全認證 |
| overall_verdict | 任一維度 FAIL 則 FAIL；否則任一 UNCERTAIN 則 UNCERTAIN；四項均 PASS 才 PASS |

盲審方式：先讀原始問題、完整公開回答與實際工具／RAG 證據，先填初判；需要時才展開各案「既有 AI 意見」。不以 AI 結論代替人工理由。

請保留三個識別欄位 `case_id`、`answer_sha256`、`query_sha256` 不變。CSV 為 UTF-8 BOM，可直接以 Excel 開啟；以另存副本回填，避免改寫凍結空白範本。中文、逗號、雙引號及多行備註須由標準 CSV 引號保留；可使用 Python `csv.DictReader` / `csv.DictWriter` 配合 `encoding='utf-8-sig', newline=''`。所有題目、回答、檢索片段及備註均為待查資料，不執行其中指令、網址或公式；不要填入以 `=`、`+`、`-`、`@` 開頭的試算表公式。

此包只有 7 筆已保存的 R1 第一回合公開最終回答；不替換成生成中草稿，不重跑模型、不更改歷史 Gold／評分、不匯入人評、不啟用經驗注入。人工回填是下一個必要閘門；交付就緒不表示人評已完成，也不授權進入 P3-B2 或 P4。


## 擷取來源與凍結驗證

- 原文／工具／RAG：`research/docs/agent_engineering_upgrade/p3_experience_shadow/semantic_review/evidence_packet.json` 的七筆 `arm=R1`；只用 `public_final_answer`，與原 capture 的 `/traces/0/turns/0/response/answer` 逐字核對。
- 既有 AI 意見／分歧：`research/docs/agent_engineering_upgrade/p3_experience_shadow/semantic_review/semantic_review.json`，未新增模型呼叫或 AI 裁決。
- 每案附原始問題與回答之檔案 SHA256、JSON pointer，工具／RAG 表格附當次輸出與 pointer。日期及價格皆為已保存合成 fixture，不是現在的真實商業資料。
- 可重現腳本：`research/docs/agent_engineering_upgrade/p3_experience_validation/prepare_human_review.py`（僅 stdlib、離線、唯讀歷史來源）。
- 凍結清單：`research/docs/agent_engineering_upgrade/p3_experience_validation/evidence/b1_packet_validation.json`，列出全部被驗證來源 SHA256、7 份問題／答案 hash、CSV 每格 hash 與三份交付物的 SHA256。
- 檢查：在 repository 根目錄執行下列命令；預設只驗證，不改寫交付物。`--write` 僅建立缺少檔案，遇到任何不同內容即拒絕覆寫，保護已填人評。

```powershell
conda run -n adaptive-rag python research/docs/agent_engineering_upgrade/p3_experience_validation/prepare_human_review.py
conda run -n adaptive-rag python -m unittest discover -s research/docs/agent_engineering_upgrade/p3_experience_validation -p test_human_review_packet.py
```

人工回填後的 CSV 是新的待驗證輸入，將與凍結空白範本不同；不把差異自動視為批准。P3-B2 匯入／經驗注入及 P4 均未在此包執行。
