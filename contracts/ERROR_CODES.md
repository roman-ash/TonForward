# Коды ошибок контракта Deal

Контракт использует числовые коды ошибок вместо строковых сообщений (требование Tact).

## Коды ошибок

### MarkPurchased (100-199)
- `101` - Deal must be FUNDED
- `102` - Only buyer can mark purchased
- `103` - Purchase deadline passed

### MarkShipped (200-299)
- `201` - Deal must be PURCHASED
- `202` - Only buyer can mark shipped
- `203` - Ship deadline passed

### ConfirmDelivery (300-399)
- `301` - Deal must be SHIPPED
- `302` - Only customer can confirm delivery

### CancelBeforePurchase (400-499)
- `401` - Deal must be FUNDED
- `402` - Purchase deadline not passed yet

### CancelBeforeShip (500-599)
- `501` - Deal must be PURCHASED
- `502` - Ship deadline not passed yet

### AutoCompleteForBuyer (600-699)
- `601` - Deal must be SHIPPED
- `602` - Confirm deadline not passed yet
- `603` - Only buyer or service can auto-complete

### ResolveDisputeRefundCustomer (700-799)
- `701` - Deal must be in DISPUTE
- `702` - Only arbiter can resolve dispute

### ResolveDisputePayBuyer (800-899)
- `801` - Deal must be in DISPUTE
- `802` - Only arbiter can resolve dispute

### ResolveDisputeSplit (900-999)
- `901` - Deal must be in DISPUTE
- `902` - Only arbiter can resolve dispute

### OpenDispute (1000-1099)
- `1001` - Invalid status for dispute
- `1002` - Only participants can open dispute

