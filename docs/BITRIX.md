# Bitrix24

Портал: https://bx.crg.im/

OAuth: заполнить `BITRIX_CLIENT_ID`, `BITRIX_CLIENT_SECRET`, `BITRIX_REDIRECT_URI`. Scope: `user`, `crm`.

Для серверной синхронизации можно заполнить `BITRIX_WEBHOOK_URL`.

Указать category ID воронок Тех интеграция, Внедрение, CR Start и Поддержка в `.env`.

Сделки синхронизируются через `crm.item.list` с `entityTypeId=2`.