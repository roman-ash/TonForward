import "@stdlib/deploy";

message MarkPurchased {}
message MarkShipped {}
message ConfirmDelivery {}
message CancelBeforePurchase {}
message CancelBeforeShip {}
message AutoCompleteForBuyer {}
message OpenDispute {}
message ResolveDisputeRefundCustomer {}
message ResolveDisputePayBuyer {}
message ResolveDisputeSplit {}

// Структура для хранения данных сделки
struct DealData {
    customer: Address;
    buyer: Address;
    serviceWallet: Address;
    arbiter: Address;
    itemPriceNano: Int as coins;
    buyerFeeNano: Int as coins;
    serviceFeeNano: Int as coins;
    insuranceNano: Int as coins;
    purchaseDeadline: Int as uint64;
    shipDeadline: Int as uint64;
    confirmDeadline: Int as uint64;
    metadataHash: Int as uint256; // Hash как uint256 вместо Slice для простоты
    status: Int as uint8; // 0=NEW, 1=FUNDED, 2=PURCHASED, 3=SHIPPED, 4=COMPLETED, 5=CANCELLED_REFUND, 6=CANCELLED_PAY, 7=DISPUTE
}

// Контракт Deal для escrow сделок
contract Deal with Deployable {
    data: DealData;

    init(
        customer: Address,
        buyer: Address,
        serviceWallet: Address,
        arbiter: Address,
        itemPriceNano: Int as coins,
        buyerFeeNano: Int as coins,
        serviceFeeNano: Int as coins,
        insuranceNano: Int as coins,
        purchaseDeadline: Int as uint64,
        shipDeadline: Int as uint64,
        confirmDeadline: Int as uint64,
        metadataHash: Int as uint256
    ) {
        self.data = DealData{
            customer: customer,
            buyer: buyer,
            serviceWallet: serviceWallet,
            arbiter: arbiter,
            itemPriceNano: itemPriceNano,
            buyerFeeNano: buyerFeeNano,
            serviceFeeNano: serviceFeeNano,
            insuranceNano: insuranceNano,
            purchaseDeadline: purchaseDeadline,
            shipDeadline: shipDeadline,
            confirmDeadline: confirmDeadline,
            metadataHash: metadataHash,
            status: 1 // FUNDED после деплоя
        };
    }

    // Байер отмечает, что товар куплен
    receive(msg: MarkPurchased) {
        if (self.data.status != 1) { throw(101); } // Deal must be FUNDED
        if (sender() != self.data.buyer) { throw(102); } // Only buyer can mark purchased
        if (now() > self.data.purchaseDeadline) { throw(103); } // Purchase deadline passed
        
        self.data.status = 2; // PURCHASED
    }

    // Байер отмечает, что товар отправлен
    receive(msg: MarkShipped) {
        if (self.data.status != 2) { throw(201); } // Deal must be PURCHASED
        if (sender() != self.data.buyer) { throw(202); } // Only buyer can mark shipped
        if (now() > self.data.shipDeadline) { throw(203); } // Ship deadline passed
        
        self.data.status = 3; // SHIPPED
    }

    // Заказчик подтверждает получение
    receive(msg: ConfirmDelivery) {
        if (self.data.status != 3) { throw(301); } // Deal must be SHIPPED
        if (sender() != self.data.customer) { throw(302); } // Only customer can confirm delivery
        
        self.data.status = 4; // COMPLETED
        
        // Распределяем средства
        send(SendParameters{
            to: self.data.buyer,
            value: self.data.itemPriceNano + self.data.buyerFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
        
        send(SendParameters{
            to: self.data.serviceWallet,
            value: self.data.serviceFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
        
        if (self.data.insuranceNano > 0) {
            send(SendParameters{
                to: self.data.customer,
                value: self.data.insuranceNano,
                mode: SendRemainingValue,
                bounce: false
            });
        }
    }

    // Отмена до покупки - возврат заказчику
    receive(msg: CancelBeforePurchase) {
        if (self.data.status != 1) { throw(401); } // Deal must be FUNDED
        if (now() <= self.data.purchaseDeadline) { throw(402); } // Purchase deadline not passed yet
        
        self.data.status = 5; // CANCELLED_REFUND_CUSTOMER
        
        let totalAmount: Int = self.data.itemPriceNano + self.data.buyerFeeNano + 
                               self.data.serviceFeeNano + self.data.insuranceNano;
        
        send(SendParameters{
            to: self.data.customer,
            value: totalAmount,
            mode: SendRemainingValue,
            bounce: false
        });
    }

    // Отмена до отправки - возврат заказчику
    receive(msg: CancelBeforeShip) {
        if (self.data.status != 2) { throw(501); } // Deal must be PURCHASED
        if (now() <= self.data.shipDeadline) { throw(502); } // Ship deadline not passed yet
        
        self.data.status = 5; // CANCELLED_REFUND_CUSTOMER
        
        let totalAmount: Int = self.data.itemPriceNano + self.data.buyerFeeNano + 
                               self.data.serviceFeeNano + self.data.insuranceNano;
        
        send(SendParameters{
            to: self.data.customer,
            value: totalAmount,
            mode: SendRemainingValue,
            bounce: false
        });
    }

    // Автоматическое завершение для байера
    receive(msg: AutoCompleteForBuyer) {
        if (self.data.status != 3) { throw(601); } // Deal must be SHIPPED
        if (now() <= self.data.confirmDeadline) { throw(602); } // Confirm deadline not passed yet
        if (sender() != self.data.buyer && sender() != self.data.serviceWallet) {
            throw(603); // Only buyer or service can auto-complete
        }
        
        self.data.status = 4; // COMPLETED
        
        send(SendParameters{
            to: self.data.buyer,
            value: self.data.itemPriceNano + self.data.buyerFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
        
        send(SendParameters{
            to: self.data.serviceWallet,
            value: self.data.serviceFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
        
        if (self.data.insuranceNano > 0) {
            send(SendParameters{
                to: self.data.customer,
                value: self.data.insuranceNano,
                mode: SendRemainingValue,
                bounce: false
            });
        }
    }

    // Разрешение спора - возврат заказчику
    receive(msg: ResolveDisputeRefundCustomer) {
        if (self.data.status != 7) { throw(701); } // Deal must be in DISPUTE
        if (sender() != self.data.arbiter) { throw(702); } // Only arbiter can resolve dispute
        
        self.data.status = 5; // CANCELLED_REFUND_CUSTOMER
        
        let totalAmount: Int = self.data.itemPriceNano + self.data.buyerFeeNano + 
                               self.data.serviceFeeNano + self.data.insuranceNano;
        
        send(SendParameters{
            to: self.data.customer,
            value: totalAmount,
            mode: SendRemainingValue,
            bounce: false
        });
    }

    // Разрешение спора - выплата байеру
    receive(msg: ResolveDisputePayBuyer) {
        if (self.data.status != 7) { throw(801); } // Deal must be in DISPUTE
        if (sender() != self.data.arbiter) { throw(802); } // Only arbiter can resolve dispute
        
        self.data.status = 6; // CANCELLED_PAY_BUYER
        
        send(SendParameters{
            to: self.data.buyer,
            value: self.data.itemPriceNano + self.data.buyerFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
        
        send(SendParameters{
            to: self.data.serviceWallet,
            value: self.data.serviceFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
    }

    // Разрешение спора - разделение средств
    receive(msg: ResolveDisputeSplit) {
        if (self.data.status != 7) { throw(901); } // Deal must be in DISPUTE
        if (sender() != self.data.arbiter) { throw(902); } // Only arbiter can resolve dispute
        
        self.data.status = 4; // COMPLETED
        
        let halfAmount: Int = (self.data.itemPriceNano + self.data.buyerFeeNano) / 2;
        
        send(SendParameters{
            to: self.data.customer,
            value: halfAmount,
            mode: SendRemainingValue,
            bounce: false
        });
        
        send(SendParameters{
            to: self.data.buyer,
            value: halfAmount,
            mode: SendRemainingValue,
            bounce: false
        });
        
        send(SendParameters{
            to: self.data.serviceWallet,
            value: self.data.serviceFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
    }

    // Открытие спора
    receive(msg: OpenDispute) {
        if (self.data.status < 1 || self.data.status > 3) { throw(1001); } // Invalid status for dispute
        if (sender() != self.data.customer && sender() != self.data.buyer) {
            throw(1002); // Only participants can open dispute
        }
        
        self.data.status = 7; // DISPUTE
    }

    // GET методы для чтения состояния
    get fun get_status(): Int {
        return self.data.status;
    }

    get fun get_data(): DealData {
        return self.data;
    }
}

