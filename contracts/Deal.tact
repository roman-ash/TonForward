import "@stdlib/deploy";
import "@stdlib/ownable";

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
    metadataHash: Slice; // 32 bytes hash
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
        metadataHash: Slice
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
    receive("mark_purchased") {
        self.require(self.data.status == 1, "Deal must be FUNDED"); // FUNDED
        self.require(context().sender == self.data.buyer, "Only buyer can mark purchased");
        
        self.data.status = 2; // PURCHASED
        self.require(self.now() <= self.data.purchaseDeadline, "Purchase deadline passed");
    }

    // Байер отмечает, что товар отправлен
    receive("mark_shipped") {
        self.require(self.data.status == 2, "Deal must be PURCHASED");
        self.require(context().sender == self.data.buyer, "Only buyer can mark shipped");
        
        self.data.status = 3; // SHIPPED
        self.require(self.now() <= self.data.shipDeadline, "Ship deadline passed");
    }

    // Заказчик подтверждает получение
    receive("confirm_delivery") {
        self.require(self.data.status == 3, "Deal must be SHIPPED");
        self.require(context().sender == self.data.customer, "Only customer can confirm delivery");
        
        self.data.status = 4; // COMPLETED
        
        // Распределяем средства
        // 1. Возвращаем itemPriceNano байеру
        send(SendParameters{
            to: self.data.buyer,
            value: self.data.itemPriceNano + self.data.buyerFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
        
        // 2. Отправляем комиссию сервиса
        send(SendParameters{
            to: self.data.serviceWallet,
            value: self.data.serviceFeeNano,
            mode: SendRemainingValue,
            bounce: false
        });
        
        // 3. Возвращаем страховку заказчику (если есть)
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
    receive("cancel_before_purchase") {
        self.require(self.data.status == 1, "Deal must be FUNDED");
        self.require(self.now() > self.data.purchaseDeadline, "Purchase deadline not passed yet");
        
        self.data.status = 5; // CANCELLED_REFUND_CUSTOMER
        
        // Возвращаем все средства заказчику
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
    receive("cancel_before_ship") {
        self.require(self.data.status == 2, "Deal must be PURCHASED");
        self.require(self.now() > self.data.shipDeadline, "Ship deadline not passed yet");
        
        self.data.status = 5; // CANCELLED_REFUND_CUSTOMER
        
        // Возвращаем все средства заказчику
        let totalAmount: Int = self.data.itemPriceNano + self.data.buyerFeeNano + 
                               self.data.serviceFeeNano + self.data.insuranceNano;
        
        send(SendParameters{
            to: self.data.customer,
            value: totalAmount,
            mode: SendRemainingValue,
            bounce: false
        });
    }

    // Автоматическое завершение для байера при истечении дедлайна подтверждения
    receive("auto_complete_for_buyer") {
        self.require(self.data.status == 3, "Deal must be SHIPPED");
        self.require(self.now() > self.data.confirmDeadline, "Confirm deadline not passed yet");
        self.require(context().sender == self.data.buyer || context().sender == self.data.serviceWallet, 
                     "Only buyer or service can auto-complete");
        
        self.data.status = 4; // COMPLETED
        
        // Распределяем средства как при подтверждении
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
    receive("resolve_dispute_refund_customer") {
        self.require(self.data.status == 7, "Deal must be in DISPUTE");
        self.require(context().sender == self.data.arbiter, "Only arbiter can resolve dispute");
        
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
    receive("resolve_dispute_pay_buyer") {
        self.require(self.data.status == 7, "Deal must be in DISPUTE");
        self.require(context().sender == self.data.arbiter, "Only arbiter can resolve dispute");
        
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
    receive("resolve_dispute_split") {
        self.require(self.data.status == 7, "Deal must be in DISPUTE");
        self.require(context().sender == self.data.arbiter, "Only arbiter can resolve dispute");
        
        self.data.status = 4; // COMPLETED (разделение средств)
        
        // Разделяем 50/50 между заказчиком и байером
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
    receive("open_dispute") {
        self.require(self.data.status >= 1 && self.data.status <= 3, "Invalid status for dispute");
        self.require(context().sender == self.data.customer || context().sender == self.data.buyer, 
                     "Only participants can open dispute");
        
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

