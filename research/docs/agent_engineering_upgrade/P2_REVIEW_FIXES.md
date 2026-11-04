# P2 final review — independent engineering regressions

Initial paired output P2-E-results.json was completed and committed at81c174fee42f89e78e8781eb1d416bb6acef39e0 before these changes. No frozen dataset/Gold or original score was edited.

Fresh reviewer identified two unrelated-to-heldout implementation regressions:

1. Generic temporal language (“之前买的商品退货规则是什么”, also “之前买的商品怎么退货”) incorrectly triggered order clarification before classification/retrieval. Reproduced RED. Context Builder now distinguishes explicit/deictic/order-state requirements from general policy/how-to verbs; plain退货/退款 without an order-state target does not require an order ID. Independent policy variants pass while original seven order references still resolve.
2. M1 loaded only default20messages even when memory_recent_messages was configured higher (up to100). Reproduced RED with25messages/window100. M1 load now honors that setting; M0 remains the original20-message fixture behavior.

Original2 tests RED; regrade exposed equivalent how-to form and that same boundary regression was included in the focused fix. No held-out sample expression or score was used for tuning. Post-fix output uses a NEW filename and recorded source commit; first output, all failures, Gold and held-out freeze stay intact. This fix has its own code/test checkpoint. All work is offline, paid calls0.
