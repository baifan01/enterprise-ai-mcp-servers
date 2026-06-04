# Driivz CPMS Operations Catalog

Flat catalog generated from the local OpenAPI snapshot. Use `operations-catalog.json` for machine parsing.

## Admin-Operators

| Method | Path | Tags | Operation ID | Summary |
| --- | --- | --- | --- | --- |
| `POST` | `/v1/accounts/{accountNumber}/billing-transactions/contracts` | Account Billing Transactions | `addContractsTransaction` | Apply contract-related charge |
| `POST` | `/v1/accounts/{accountNumber}/billing-transactions/credits` | Account Billing Transactions | `addCreditTransaction` | Apply credit or debit |
| `POST` | `/v1/accounts/{accountNumber}/billing-transactions/estimation` | Account Billing Transactions | `connectorEstimatedCostCalculation_1` | Calculate estimated transaction cost for the account and connector |
| `POST` | `/v1/accounts/{accountNumber}/billing-transactions/externalPayments` | Account Billing Transactions | `addExternalPaymentTransaction` | Apply external payment |
| `POST` | `/v1/accounts/{accountNumber}/billing-transactions/filter` | Account Billing Transactions | `filterTransactions_4` | Finds billing transactions |
| `POST` | `/v1/accounts/{accountNumber}/billing-transactions/penalties` | Account Billing Transactions | `addPenaltyTransaction` | Apply penalty |
| `POST` | `/v1/accounts/{accountNumber}/billing-transactions/refunds` | Account Billing Transactions | `addRefundTransaction` | Apply refund |
| `GET` | `/v1/accounts/{accountNumber}/billing-transactions/{id}` | Account Billing Transactions | `getTransaction` | Get billing transaction details |
| `GET` | `/v1/accounts/{accountNumber}/billing-transactions/{id}/lineItems` | Account Billing Transactions | `getLineItemForTransaction` | Get line item details of billing transaction |
| `POST` | `/v1/accounts/{accountNumber}/cards/actions/order` | Account Cards | `orderCard` | Order card |
| `POST` | `/v1/accounts/{accountNumber}/cards/allowed-for-start-transaction/filter` | Account Cards | `filterAllowedCardsForStartTransaction` | Filter cards that are allowed for start transaction with connector for account |
| `POST` | `/v1/accounts/{accountNumber}/cards/batch/assign` | Account Cards | `batchAssign` | Assign batch of cards |
| `POST` | `/v1/accounts/{accountNumber}/cards/suspend` | Account Cards | `suspendCards` | Suspend cards |
| `POST` | `/v1/accounts/{accountNumber}/cards/type/echarge/assign` | Account Cards | `echargeAssign` | Assign eCharge card |
| `POST` | `/v1/accounts/{accountNumber}/cards/type/vehicleId/assign` | Account Cards | `vehicleIdCardAssign` | Assign vehicle ID |
| `POST` | `/v1/accounts/{accountNumber}/charger-operations/chargers/{chargerIdentityKey}/connectors/{connectorIdentityKey}/auto-charge/enroll` | Account Charger Operations | `autoCharge` | Enroll for autocharge |
| `POST` | `/v1/accounts/{accountNumber}/charging-ability/charging/status` | Account Charging Capabilities | `validateChargingStartStatus` | Validate customer can charge at charger |
| `POST` | `/v1/accounts/{accountNumber}/charging-ability/reservation/status` | Account Charging Capabilities | `validateChargingAbilityReservation` | Validate customer can reserve charger |
| `GET` | `/v1/accounts/{accountNumber}/charging-ability/status` | Account Charging Capabilities | `validateAccountBeforeCharging` | Validate customer account |
| `POST` | `/v1/accounts/{accountNumber}/contracts` | Account Contracts | `addContract` | Add contract |
| `GET` | `/v1/accounts/{accountNumber}/contracts/ad-hoc` | Account Ad-hoc Contracts | `getAdHocContract` | Get ad hoc contract details |
| `POST` | `/v1/accounts/{accountNumber}/contracts/ad-hoc` | Account Ad-hoc Contracts | `addAdHocContract` | Add ad hoc contract |
| `PATCH` | `/v1/accounts/{accountNumber}/contracts/ad-hoc/credit` | Account Ad-hoc Contracts | `updateAdHocContractCredit` | Update ad hoc credit amount |
| `PATCH` | `/v1/accounts/{accountNumber}/contracts/ad-hoc/status` | Account Ad-hoc Contracts | `updateAdHocContractStatus` | Update ad hoc contract status |
| `POST` | `/v1/accounts/{accountNumber}/contracts/filter` | Account Contracts | `filterContracts_1` | Find contracts |
| `GET` | `/v1/accounts/{accountNumber}/contracts/{contractId}` | Account Contracts | `getContract` | Get contract details |
| `PATCH` | `/v1/accounts/{accountNumber}/contracts/{contractId}` | Account Contracts | `updateContract` | Update contract |
| `PATCH` | `/v1/accounts/{accountNumber}/contracts/{contractId}/close` | Account Contracts | `closeContract` | Close contract |
| `PATCH` | `/v1/accounts/{accountNumber}/contracts/{contractId}/credit` | Account Contracts | `updateContractUsageCredit` | Update usage credit of contract |
| `PATCH` | `/v1/accounts/{accountNumber}/contracts/{contractId}/status` | Account Contracts | `updateContractStatus` | Update status of contract |
| `PATCH` | `/v1/accounts/{accountNumber}/contracts/{contractId}/swap` | Account Contracts | `swapContract` | Swap contract |
| `POST` | `/v1/accounts/{accountNumber}/customer-contracts/sponsored` | Account Contracts | `addSponsoredContract` | Add sponsored contract |
| `POST` | `/v1/accounts/{accountNumber}/invoices/current/pdf` | Account Invoices | `getCurrentStatementAsPdf_1` | Get current invoice as pdf |
| `POST` | `/v1/accounts/{accountNumber}/invoices/filter` | Account Invoices | `filterInvoices_1` | Find invoices |
| `POST` | `/v1/accounts/{accountNumber}/invoices/{id}/markInvoiceAsPaid` | Account Invoices | `markInvoiceAsPaid` | Mark invoice as paid |
| `GET` | `/v1/accounts/{accountNumber}/invoices/{id}/pdf` | Account Invoices | `getInvoicePdf_1` | Get invoice as PDF |
| `POST` | `/v1/accounts/{accountNumber}/invoices/{id}/writeOffInvoice` | Account Invoices | `writeOffInvoice` | Write off invoice |
| `GET` | `/v1/accounts/{accountNumber}/payment-methods/bank-account` | Account Payment Methods | `getBankAccountPayments` | Get bank account payment method details |
| `GET` | `/v1/accounts/{accountNumber}/payment-methods/payment-cards` | Account Payment Methods | `getPaymentCard` | Get card payment method details |
| `POST` | `/v1/accounts/{accountNumber}/payment-methods/payment-cards` | Account Payment Methods | `addCardPaymentMethod` | Add card payment method |
| `POST` | `/v1/accounts/{accountNumber}/payment-methods/payment-cards/no-pay` | Account Payment Methods | `addNoPayCardPaymentMethod` | Add no-pay card payment method |
| `DELETE` | `/v1/accounts/{accountNumber}/payment-methods/payment-cards/{id}` | Account Payment Methods | `deleteCreditCard` | Delete card payment method |
| `PATCH` | `/v1/accounts/{accountNumber}/payment-methods/payment-cards/{id}/primary` | Account Payment Methods | `setPrimaryPaymentCard` | Set payment card as primary |
| `POST` | `/v1/accounts/{accountNumber}/reservations/by-date` | Account Reservations | `createReservationByDate` | Reserve charger in future |
| `POST` | `/v1/accounts/{accountNumber}/reservations/chargers` | Account Reservations | `getChargerForReservation` | Find chargers |
| `POST` | `/v1/accounts/{accountNumber}/reservations/now` | Account Reservations | `reserveNow` | Reserve charger now |
| `POST` | `/v1/accounts/{accountNumber}/reservations/terms/byDate` | Account Reservations | `getReservationTermsByDate` | Get terms for future reservation |
| `POST` | `/v1/accounts/{accountNumber}/reservations/terms/now` | Account Reservations | `getReservationTermsNow` | Get terms for immediate reservation |
| `PATCH` | `/v1/accounts/{accountNumber}/reservations/{id}/cancel` | Account Reservations | `cancelReservation_1` | Cancel reservation |
| `POST` | `/v1/accounts/{accountNumber}/statements/filter` | Account Invoices | `filterStatements_1` | Find statements |
| `POST` | `/v1/authentication/operator/customer-login` | Authentication | `operatorLoginAsCustomer` | Operator login as customer |
| `POST` | `/v1/authentication/operator/login` | Authentication | `operatorLogin` | Operator login |
| `POST` | `/v1/authorization/user/{id}/generate` | User Authorize | `generateUserAuthorization` | Generate user authorization code |
| `POST` | `/v1/billing-transactions/filter` | Billing Transactions | `filterTransactions_3` | Find billing transactions |
| `POST` | `/v1/billing-transactions/one-time-payment/estimation` | Billing Transactions | `connectorEstimatedCostCalculation` | Calculate estimated transaction cost from one time payment driver |
| `POST` | `/v1/cards/batch/import` | Cards | `importBatch` | Import batch of cards |
| `GET` | `/v1/cards/batch/{id}` | Cards | `getCardIdsFromBatch` | Get card IDs |
| `POST` | `/v1/cards/filter` | Cards | `filterCards` | Find cards |
| `GET` | `/v1/cards/{id}` | Cards | `getCard` | Get card details |
| `PATCH` | `/v1/cards/{id}/actions/attach` | Cards | `attachCard` | Connect cards |
| `POST` | `/v1/cards/{id}/activate` | Cards | `activateCard` | Activate card |
| `PATCH` | `/v1/cards/{id}/delete` | Cards | `deleteCardById` | Delete card |
| `POST` | `/v1/cards/{id}/reassign` | Cards | `reassign` | Reassign card |
| `PATCH` | `/v1/cards/{id}/status` | Cards | `changeStatus` | Update card status |
| `GET` | `/v1/charger-groups/root` | Charger Groups | `getChargerRootGroup` | Find root group |
| `DELETE` | `/v1/charger-groups/{id}` | Charger Groups | `deleteChargerGroupById` | Delete charger group |
| `GET` | `/v1/charger-groups/{id}` | Charger Groups | `getChargerGroupById` | Get charger group details |
| `PATCH` | `/v1/charger-groups/{id}` | Charger Groups | `updateChargerGroup` | Update charger group |
| `POST` | `/v1/charger-groups/{id}` | Charger Groups | `addChargerGroup` | Create charger group |
| `PATCH` | `/v1/charger-groups/{id}/billing-plans/add` | Charger Groups | `addBillingPlansToGroup` | Add billing plans |
| `PATCH` | `/v1/charger-groups/{id}/billing-plans/remove` | Charger Groups | `removeBillingPlansFromGroup` | Remove billing plans |
| `GET` | `/v1/charger-groups/{id}/chargers` | Charger Groups | `getChargerGroupChargersById` | Get charger details |
| `PATCH` | `/v1/charger-groups/{id}/chargers/add` | Charger Groups | `addChargersToGroup` | Add chargers |
| `PATCH` | `/v1/charger-groups/{id}/chargers/remove` | Charger Groups | `removeChargersFromGroup` | Remove chargers |
| `POST` | `/v1/charger-groups/{id}/folder` | Charger Groups | `addChargerGroupFolder` | Create folder |
| `PATCH` | `/v1/charger-groups/{id}/reallocation` | Charger Groups | `reallocateChargerGroup` | Reallocate chargers |
| `POST` | `/v1/charger-hosts` | Charger Hosts | `createChargerHost` | Create charger host |
| `POST` | `/v1/charger-hosts/filter` | Charger Hosts | `filterChargerHosts` | Find charger hosts |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/actions/activate` | Charger Hosts | `activateChargerHostProfile` | Activate account |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/actions/close` | Charger Hosts | `closeChargerHostProfile` | Close account |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/actions/reopen` | Charger Hosts | `reopenChargerHostProfile` | Reopen account |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/actions/suspend` | Charger Hosts | `suspendChargerHostProfile` | Suspend account |
| `GET` | `/v1/charger-hosts/{accountNumber}/billing` | Charger Hosts | `getChargerHostBilling` | Get customer plan and contract details |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/billing` | Charger Hosts | `updateChargerHostBilling` | Update customer plan and contract details |
| `POST` | `/v1/charger-hosts/{accountNumber}/billing-transactions/filter` | Charger Host Transactions | `filterTransactions_2` | Find transactions |
| `DELETE` | `/v1/charger-hosts/{accountNumber}/country-currency/{countryCurrency}/entity` | Charger Hosts | `deleteChargerHostEntity` | Delete a charger host entity |
| `GET` | `/v1/charger-hosts/{accountNumber}/country-currency/{countryCurrency}/entity` | Charger Hosts | `getChargerHostEntity_1` | Find charger host entity by account number and country-currency |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/country-currency/{countryCurrency}/entity` | Charger Hosts | `updateChargerHostEntity_1` | Update a charger host entity by account number and country-currency |
| `GET` | `/v1/charger-hosts/{accountNumber}/currencies/{currency}/wallet` | Charger Hosts | `getChargerHostAccount_1` | Get billing details using currency |
| `GET` | `/v1/charger-hosts/{accountNumber}/entity` | Charger Hosts | `getChargerHostEntity` | Find charger host entity by account number |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/entity` | Charger Hosts | `updateChargerHostEntity` | Update a charger host entity by account number |
| `POST` | `/v1/charger-hosts/{accountNumber}/invoices/current/pdf` | Charger Host Invoices | `getCurrentStatementAsPdf` | Get current invoice as PDF |
| `POST` | `/v1/charger-hosts/{accountNumber}/invoices/filter` | Charger Host Invoices | `filterInvoices` | Find invoices |
| `GET` | `/v1/charger-hosts/{accountNumber}/invoices/{id}/pdf` | Charger Host Invoices | `getInvoicePdf` | Get invoice as PDF |
| `GET` | `/v1/charger-hosts/{accountNumber}/payment-gateway` | Charger Hosts | `getChargerHostPaymentGateway` | Get payment gateway details |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/payment-gateway` | Charger Hosts | `updateChargerHostPaymentGateway` | Update payment gateway details |
| `GET` | `/v1/charger-hosts/{accountNumber}/plan-management` | Charger Hosts | `getChargerHostPlanManagement` | Get plan management details |
| `GET` | `/v1/charger-hosts/{accountNumber}/profile` | Charger Hosts | `getChargerHostProfile` | Get profile details |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/profile` | Charger Hosts | `updateChargerHostProfile` | Update profile details |
| `POST` | `/v1/charger-hosts/{accountNumber}/statements/filter` | Charger Host Statements | `filterStatements` | Find statements |
| `GET` | `/v1/charger-hosts/{accountNumber}/wallet` | Charger Hosts | `getChargerHostAccount` | Get billing details |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/wallet/billing-info` | Charger Hosts | `updateWalletBillingInfo` | Update billing information |
| `PATCH` | `/v1/charger-hosts/{accountNumber}/wallet/block-settings` | Charger Hosts | `updateWalletBlockSettings` | Update block settings |
| `GET` | `/v1/charger-hosts/{id}/plans` | Charger Hosts | `getChargerHostPlans` | Get charging plans of host |
| `PATCH` | `/v1/charger-hosts/{id}/plans/add` | Charger Hosts | `addChargerHostPlans` | Assign charging plans to a host |
| `PATCH` | `/v1/charger-hosts/{id}/plans/remove` | Charger Hosts | `removeChargerHostPlans` | Remove charging plans from host |
| `POST` | `/v1/charger-model-presets/filter` | Charger Model Presets | `filterChargerModelPresets` | Find charger model presets |
| `POST` | `/v1/charger-models` | Charger Models | `createChargerModel` | Create charger model |
| `POST` | `/v1/charger-models/filter` | Charger Models | `filterChargerModel` | Find charger models |
| `DELETE` | `/v1/charger-models/{id}` | Charger Models | `deleteModel` | Delete charger model |
| `GET` | `/v1/charger-models/{id}` | Charger Models | `getChargerModel` | Get charger model details |
| `PATCH` | `/v1/charger-models/{id}` | Charger Models | `updateChargerModel` | Update charger model |
| `POST` | `/v1/charger-models/{id}/connectors` | Charger Model Connectors | `createChargerModelConnector` | Add connector |
| `DELETE` | `/v1/charger-models/{id}/connectors/{connectorId}` | Charger Model Connectors | `deleteChargerModelConnector` | Delete connector |
| `PATCH` | `/v1/charger-models/{id}/connectors/{connectorId}` | Charger Model Connectors | `updateChargerModelConnector` | Update connector |
| `DELETE` | `/v1/charger-models/{id}/images/{imageId}` | Charger Model Images | `deleteChargerModelImage` | Delete image |
| `GET` | `/v1/charger-models/{id}/images/{imageId}` | Charger Model Images | `findResource` | Get image |
| `POST` | `/v1/charger-models/{id}/images/{resourceId}` | Charger Model Images | `addImageToChargerModel` | Add image |
| `POST` | `/v1/charger-models/{id}/protocols` | Charger Model Protocol | `createModelProtocol` | Add protocol |
| `DELETE` | `/v1/charger-models/{id}/protocols/{protocolId}` | Charger Model Protocol | `deleteModelProtocol` | Delete protocol |
| `PATCH` | `/v1/charger-models/{id}/protocols/{protocolId}` | Charger Model Protocol | `updateModelProtocol` | Update protocol |
| `POST` | `/v1/chargers` | Chargers | `addCharger` | Add charger |
| `POST` | `/v1/chargers/batch` | Chargers | `addChargers` | Create batch of chargers |
| `POST` | `/v1/chargers/connection-log/filter` | Chargers | `filterChargerConnectionLog` | Find charger connection logs |
| `POST` | `/v1/chargers/connectors/{connectorId}/remote-operations/one-time-payment-start-transaction` | Charger Remote Operations | `startOneTImePaymentTransaction` | Send guest driver start transaction command |
| `PATCH` | `/v1/chargers/connectors/{connectorId}/remote-operations/one-time-payment-stop-transaction` | Charger Remote Operations | `stopOneTimePaymentTransaction` | Send guest driver stop transaction command |
| `POST` | `/v1/chargers/connectors/{connectorId}/remote-operations/start-transaction` | Charger Remote Operations | `startTransaction` | Send start transaction command |
| `PATCH` | `/v1/chargers/connectors/{connectorId}/remote-operations/start-transaction-by-card-number` | Charger Remote Operations | `startTransactionByCardNumber` | Send start transaction command with card number |
| `PATCH` | `/v1/chargers/connectors/{connectorId}/remote-operations/stop-transaction` | Charger Remote Operations | `stopTransaction` | Send stop transaction command |
| `PATCH` | `/v1/chargers/connectors/{connectorId}/remote-operations/stop-transaction-by-card-number` | Charger Remote Operations | `stopTransactionByCardNumber` | Send stop transaction command with card number |
| `POST` | `/v1/chargers/connectors/{connectorId}/remote-operations/unlock` | Charger Remote Operations | `unlockConnector` | Send unlock command |
| `POST` | `/v1/chargers/detailed-log/chargers/{identityKey}` | Chargers | `findChargerDetailedLogsByIdentityKey` | Find charger detailed logs by identity key |
| `POST` | `/v1/chargers/detailed-log/filter` | Chargers | `filterChargerDetailedLogs` | Find charger detailed logs |
| `POST` | `/v1/chargers/electrical/filter` | Chargers | `filterChargerElectrical` | Find electrical details |
| `PATCH` | `/v1/chargers/evses/{evseId}/remote-operations/start-transaction-by-card-number` | Charger Remote Operations | `startEvseTransactionByCardNumber` | Send start EVSE transaction command with card number |
| `POST` | `/v1/chargers/groups/{groupId}/remote-operations/raw` | Charger Group Remote Operations | `sendRawMessage_1` | Send remote operation |
| `POST` | `/v1/chargers/history/address/filter` | Chargers | `filter_10` | Find charger address history |
| `POST` | `/v1/chargers/history/filter` | Chargers | `filter_9` | Find charger history |
| `POST` | `/v1/chargers/identity-key/{identityKey}/history/filter` | Chargers | `filterByIdentityKey` | Find charger history |
| `POST` | `/v1/chargers/locations/filter` | Chargers | `filterChargerLocation` | Find charger locations |
| `POST` | `/v1/chargers/maintenance/filter` | Chargers | `filterChargerMaintenance` | Find maintenance details |
| `POST` | `/v1/chargers/networks/filter` | Chargers | `filterChargerNetwork` | Find network details |
| `POST` | `/v1/chargers/profiles/filter` | Chargers | `filterChargerProfile` | Find profile details |
| `POST` | `/v1/chargers/statuses/filter` | Chargers | `filterChargerStatus` | Find status details |
| `POST` | `/v1/chargers/{chargerIdentityKey}/presets/{presetId}/apply` | Charger Remote Operations | `applyChargerModelPreset` | Apply preset for charger by identity key and preset id |
| `GET` | `/v1/chargers/{chargerId}/configurations/history` | Charger Configuration | `getConfigurationHistory` | Get charger configuration change history |
| `POST` | `/v1/chargers/{chargerId}/connectors/{connectorId}/parking` | Charger Connectors | `createConnectorParking` | Add vehicle access information |
| `DELETE` | `/v1/chargers/{chargerId}/connectors/{connectorId}/parking/{parkingId}` | Charger Connectors | `deleteConnectorParking` | Delete vehicle access information |
| `GET` | `/v1/chargers/{chargerId}/connectors/{connectorId}/parking/{parkingId}` | Charger Connectors | `getConnectorParking` | Get vehicle access information |
| `PATCH` | `/v1/chargers/{chargerId}/connectors/{connectorId}/parking/{parkingId}` | Charger Connectors | `updateConnectorParking` | Update vehicle access information |
| `GET` | `/v1/chargers/{chargerId}/connectors/{connectorId}/tariffs` | Charger Connectors | `getConnectorTariff` | Get connector tariffs |
| `PATCH` | `/v1/chargers/{chargerId}/connectors/{connectorId}/tariffs` | Charger Connectors | `updateConnectorTariff` | Update connector tariffs |
| `POST` | `/v1/chargers/{identityKey}/evses/{evseId}/allowed` | Chargers Compound | `validateChargerConnectorEvseReplacement` | Validates whether the EVSE ID can be updated on a charger |
| `POST` | `/v1/chargers/{identityKey}/remote-operations/charging-profile` | Charger Remote Operations | `sendChargingProfileMessage` | Send charging profile |
| `POST` | `/v1/chargers/{identityKey}/remote-operations/configuration` | Charger Remote Operations | `sendChangeConfigurationMessage` | Send update configuration |
| `POST` | `/v1/chargers/{identityKey}/remote-operations/configuration/filter` | Charger Remote Operations | `findChargerConfigurationByFilter` | Get charger configuration by filter |
| `POST` | `/v1/chargers/{identityKey}/remote-operations/get-diagnostics` | Charger Remote Operations | `sendGetDiagnosticsMessage` | Send get diagnostics command |
| `POST` | `/v1/chargers/{identityKey}/remote-operations/raw` | Charger Remote Operations | `sendRawMessage` | Send raw message |
| `POST` | `/v1/chargers/{identityKey}/remote-operations/reset` | Charger Remote Operations | `sendResetMessage` | Send reset command |
| `DELETE` | `/v1/chargers/{id}` | Chargers | `deleteCharger` | Delete charger |
| `PATCH` | `/v1/chargers/{id}/actions/move-from-warehouse` | Chargers Compound | `moveChargerFromWarehouse` | Move charger from warehouse |
| `PATCH` | `/v1/chargers/{id}/actions/move-to-warehouse` | Chargers Compound | `moveChargerToWarehouse` | Move charger to warehouse |
| `PATCH` | `/v1/chargers/{id}/actions/replacement` | Chargers Compound | `replacement` | Replace a Charger with stored warehouse charger |
| `GET` | `/v1/chargers/{id}/charger-groups` | Charger Groups | `getGroupsByChargerId` | Find charger groups |
| `PATCH` | `/v1/chargers/{id}/connectors/{connectorId}` | Charger Connectors | `updateChargerConnector` | Update connector details |
| `PATCH` | `/v1/chargers/{id}/connectors/{connectorId}/actions/manual-status-update` | Charger Connectors | `manualStatusUpdate` | Update connector status |
| `PATCH` | `/v1/chargers/{id}/connectors/{connectorId}/evse` | Charger Connectors | `updateChargerConnectorEvse` | Update EVSE details |
| `GET` | `/v1/chargers/{id}/electrical` | Chargers | `getChargerElectrical` | Get charger's electrical details |
| `PATCH` | `/v1/chargers/{id}/electrical` | Chargers | `updateChargerElectrical` | Update charger's electrical details |
| `GET` | `/v1/chargers/{id}/location` | Chargers | `getChargerLocation` | Get charger's location |
| `PATCH` | `/v1/chargers/{id}/location` | Chargers | `updateChargerLocation` | Update charger's location |
| `GET` | `/v1/chargers/{id}/maintenance` | Chargers | `getChargerMaintenance` | Get charger's maintenance details |
| `PATCH` | `/v1/chargers/{id}/maintenance` | Chargers | `updateChargerMaintenance` | Update charger’s maintenance details |
| `PATCH` | `/v1/chargers/{id}/maintenance/actions/schedule-one-time-maintenance-date` | Chargers | `updateChargerMaintenanceNextDate` | Update next charger maintenance  date |
| `GET` | `/v1/chargers/{id}/network` | Chargers | `getChargerNetwork` | Get charger’s network details |
| `PATCH` | `/v1/chargers/{id}/network` | Chargers | `updateChargerNetwork` | Update charger's network details |
| `GET` | `/v1/chargers/{id}/profile` | Chargers | `getChargerProfile` | Get charger’s profile details |
| `PATCH` | `/v1/chargers/{id}/profile` | Chargers | `updateChargerProfile` | Update charger's profile details |
| `PATCH` | `/v1/chargers/{id}/provision/status/change` | Chargers | `changeProvisionStatusByChargerId` | Update charger's provision status |
| `PATCH` | `/v1/chargers/{id}/set-connection-password` | Chargers | `setConnectionPassword` | Set charger connection password |
| `GET` | `/v1/chargers/{id}/status` | Chargers | `getChargerStatus` | Get charger's status |
| `PATCH` | `/v1/chargers/{id}/status/actions/decommission` | Chargers | `decommissionCharger` | Update charger's status to decommissioned |
| `PATCH` | `/v1/chargers/{id}/status/actions/provision` | Chargers | `provisionCharger` | Update charger's status to provisioned |
| `POST` | `/v1/companies` | Companies | `addCompany` | Add company |
| `POST` | `/v1/companies/filter` | Companies | `filter_8` | Find companies |
| `DELETE` | `/v1/companies/{id}` | Companies | `deleteCompany` | Delete company |
| `GET` | `/v1/companies/{id}` | Companies | `getCompany` | Get company details |
| `PATCH` | `/v1/companies/{id}` | Companies | `updateCompany` | Update company |
| `POST` | `/v1/companies/{id}/person/add` | Companies | `addPersonToCompany` | Add person to company |
| `POST` | `/v1/companies/{id}/person/remove` | Companies | `removePersonFromCompany` | Remove person from company |
| `GET` | `/v1/configurations/external-card-authorization-providers` | Configurations | `getExternalCardAuthorizationProvider` | Get external card authorization providers |
| `POST` | `/v1/configurations/filter` | Configurations | `filter_7` | Find configuration parameters |
| `GET` | `/v1/configurations/{id}` | Configurations | `getConfigurationById` | Get configuration parameter |
| `PATCH` | `/v1/configurations/{id}` | Configurations | `update_1` | Update configuration parameter |
| `POST` | `/v1/connector-types/filter` | Connector Types | `filter_6` | Find connector types |
| `POST` | `/v1/contact-people` | Contact People | `createPerson` | Create contact person |
| `POST` | `/v1/contact-people/filter` | Contact People | `filterContactPeople` | Find contact people |
| `GET` | `/v1/contact-people/{id}` | Contact People | `getContactPerson` | Get contact person details |
| `POST` | `/v1/country-currencies/filter` | Country Currencies | `filter_5` | Find country currencies |
| `GET` | `/v1/country-currencies/{id}` | Country Currencies | `getCountryCurrency` | Get country currency details |
| `POST` | `/v1/custom-integrations/cdrs/filter` | Custom Integrations | `filter_4` | Find EV transactions in cdr format |
| `POST` | `/v1/customer-accounts` | Customer Accounts | `addCustomer` | Create customer account |
| `POST` | `/v1/customer-accounts/filter` | Customer Accounts | `filterCustomerAccounts` | Find accounts |
| `POST` | `/v1/customer-accounts/members/filter` | Customer Member Accounts | `filterMembers` | Find members |
| `DELETE` | `/v1/customer-accounts/members/{accountNumber}` | Customer Member Accounts | `deleteMemberByAccountNumber` | Delete member |
| `PATCH` | `/v1/customer-accounts/members/{accountNumber}/actions/suspend` | Customer Member Accounts | `suspendMemberByAccountNumber` | Suspend member |
| `PATCH` | `/v1/customer-accounts/members/{accountNumber}/actions/unsuspend` | Customer Member Accounts | `unsuspendMemberByAccountNumber` | Restore member |
| `GET` | `/v1/customer-accounts/members/{accountNumber}/profile` | Customer Member Accounts | `getMember` | Get member details |
| `PATCH` | `/v1/customer-accounts/members/{accountNumber}/profile` | Customer Member Accounts | `updateMemberByAccountNumber` | Update member details |
| `POST` | `/v1/customer-accounts/no-billing-info` | Customer Accounts | `addCustomerWithoutBillingInfo` | Create customer account |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/actions/activate` | Customer Accounts | `activateRegisteredAccount` | Activate account |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/actions/close` | Customer Accounts | `close` | Close account |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/actions/reopen` | Customer Accounts | `reopenAccount` | Reopen account |
| `GET` | `/v1/customer-accounts/{accountNumber}/notifications-preferences` | Customer Accounts | `getNotificationPreferences` | Get notification preferences |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/notifications-preferences` | Customer Accounts | `updateNotificationPreferences_1` | Update notification preferences |
| `GET` | `/v1/customer-accounts/{accountNumber}/profile` | Customer Accounts | `getCustomerAccount` | Get customer account details |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/profile` | Customer Accounts | `updateCustomerProfile` | Update customer account details |
| `GET` | `/v1/customer-accounts/{accountNumber}/wallet` | Customer Accounts | `getAccountWallet` | Get account wallet |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/wallet` | Customer Accounts | `updateCustomerWallet` | Update account wallet |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/wallet/billing-cycle` | Customer Accounts | `updateAccountBillingCycle` | Update billing cycle |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/wallet/block-settings` | Customer Accounts | `updateAccountWalletBlockSettings` | Update block settings |
| `PATCH` | `/v1/customer-accounts/{accountNumber}/wallet/charging-configuration` | Customer Accounts | `updateChargingConfiguration` | Update charging configuration |
| `POST` | `/v1/customer-accounts/{payingAccountNumber}/members` | Customer Member Accounts | `addMember` | Add member |
| `POST` | `/v1/customer-contracts/filter` | Customer Contracts | `filterContracts` | Find contracts |
| `POST` | `/v1/customer-contracts/host/account/{chargerHostAccountNumber}/department/{departmentId}/drivers/contracts` | Customer Contracts | `createContractToDepartmentGroupOfDrivers` | Create a contract to a department of drivers |
| `POST` | `/v1/customer-contracts/host/account/{chargerHostAccountNumber}/drivers/contracts` | Customer Contracts | `createContractToHostDrivers` | Create a contract to host drivers |
| `POST` | `/v1/customer-plans` | Customer Plans | `createPlan` | Create plan |
| `POST` | `/v1/customer-plans/profiles/filter` | Customer Plans | `filterPlanProfile` | Find profiles |
| `PATCH` | `/v1/customer-plans/{planCode}/activate` | Customer Plans | `activatePlan` | Activate plan |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/activate` | Customer Plans | `activatePlanByCountryCurrency` | Activate plan with country currency |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/deactivate` | Customer Plans | `deactivatePlanByCountryCurrency` | Deactivate plan with country currency |
| `GET` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/display` | Customer Plan Displays | `getPlanDisplayByCodeCountryCurrency` | Get plan display details with country currency |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/display` | Customer Plan Displays | `updatePlanDisplayByCodeCountryCurrency` | Update plan display details with country currency |
| `GET` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility` | Customer Plans Eligibility (Deprecated) | `getPlanEligibilityByCountryCurrency_1` | Get a customer plan eligibility by plan code and country-currency with pagination support |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility` | Customer Plans Eligibility (Deprecated) | `updatePlanEligibility_1` | Update a customer plan eligibility by plan code and country-currency |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/disable` | Customer Plans Eligibility (Deprecated) | `disablePlanEligibility_2` | Disable customer plan eligibility by plan code and country-currency |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/enable` | Customer Plans Eligibility (Deprecated) | `enablePlanEligibility_2` | Enable customer plan eligibility by plan code and country-currency |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/identifiers` | Customer Plans Eligibility (Deprecated) | `addPlanEligibilityIdentifiers_2` | Add identifiers to a customer plan eligibility by plan code and country-currency |
| `DELETE` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/identifiers/{identifierId}` | Customer Plans Eligibility (Deprecated) | `deletePlanEligibilityIdentifier_2` | Delete an identifier from plan eligibility by plan code and country-currency |
| `GET` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/registration-display` | Customer Plan Displays | `getPlanRegistrationDisplayByCountryCurrency` | Get plan registration display details with country currency |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/registration-display` | Customer Plan Displays | `updatePlanRegistrationDisplayByCountryCurrency` | Update plan registration display details with country currency |
| `GET` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/products` | Customer Plan Products | `getBillingPlanProductsByCountryCurrency` | Get plan products with country currency |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/products/update` | Customer Plan Products | `updatePlanProduct_1` | Update plan products with country currency |
| `GET` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/profile` | Customer Plans | `getPlanProfileByCountryCurrency` | Get profile details with country currency |
| `PATCH` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/profile` | Customer Plans | `updatePlanByCountryCurrency` | Update profile details with country currency |
| `GET` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/tariffs/charger-groups/all` | Customer Plan Tariffs | `getBillingPlanTariffsForAllGroupsByCodeCountryCurrency` | Get plan tariff details for all charger groups with specific country currency |
| `GET` | `/v1/customer-plans/{planCode}/country-currency/{countryCurrency}/tariffs/charger-groups/{chargerGroupId}` | Customer Plan Tariffs | `getBillingPlanGroupTariffsByCodeCountryCurrency` | Get plan tariff details for specific charger group and country currency |
| `PATCH` | `/v1/customer-plans/{planCode}/deactivate` | Customer Plans | `deactivatePlan` | Deactivate plan |
| `GET` | `/v1/customer-plans/{planCode}/discount` | Customer Plans Discount | `getPlanDiscountByCode` | Get plan discount details |
| `PATCH` | `/v1/customer-plans/{planCode}/discount` | Customer Plans Discount | `updatePlanDiscountByCode` | Update plan discount details |
| `GET` | `/v1/customer-plans/{planCode}/locales/{locale}/display` | Customer Plan Displays | `getPlanDisplayByCode` | Get plan display details |
| `PATCH` | `/v1/customer-plans/{planCode}/locales/{locale}/display` | Customer Plan Displays | `updatePrimaryPlanDisplay` | Update plan display details |
| `GET` | `/v1/customer-plans/{planCode}/locales/{locale}/eligibility` | Customer Plans Eligibility (Deprecated) | `getPlanEligibility_1` | Get a customer plan eligibility by plan code with pagination support |
| `PATCH` | `/v1/customer-plans/{planCode}/locales/{locale}/eligibility` | Customer Plans Eligibility (Deprecated) | `updatePlan_1` | Update a customer plan eligibility by plan code |
| `PATCH` | `/v1/customer-plans/{planCode}/locales/{locale}/eligibility/disable` | Customer Plans Eligibility (Deprecated) | `disablePlanEligibility_1` | Disable customer plan eligibility |
| `PATCH` | `/v1/customer-plans/{planCode}/locales/{locale}/eligibility/enable` | Customer Plans Eligibility (Deprecated) | `enablePlanEligibility_1` | Enable customer plan eligibility |
| `PATCH` | `/v1/customer-plans/{planCode}/locales/{locale}/eligibility/identifiers` | Customer Plans Eligibility (Deprecated) | `addPlanEligibilityIdentifiers_1` | Add identifiers to a customer plan eligibility by plan code |
| `DELETE` | `/v1/customer-plans/{planCode}/locales/{locale}/eligibility/identifiers/{identifierId}` | Customer Plans Eligibility (Deprecated) | `deletePlanEligibilityIdentifier_1` | Delete an identifier from plan eligibility by plan code |
| `GET` | `/v1/customer-plans/{planCode}/locales/{locale}/registration-display` | Customer Plan Displays | `getPlanRegistrationDisplay` | Get plan registration display details |
| `PATCH` | `/v1/customer-plans/{planCode}/locales/{locale}/registration-display` | Customer Plan Displays | `updatePlanRegistrationDisplay` | Update plan registration display details |
| `GET` | `/v1/customer-plans/{planCode}/products` | Customer Plan Products | `getBillingPlanProducts` | Get products |
| `POST` | `/v1/customer-plans/{planCode}/products` | Customer Plan Products | `addPlanProduct` | Add product |
| `PATCH` | `/v1/customer-plans/{planCode}/products/remove` | Customer Plan Products | `removePlanProduct` | Remove product |
| `PATCH` | `/v1/customer-plans/{planCode}/products/update` | Customer Plan Products | `updatePlanProduct` | Update product |
| `GET` | `/v1/customer-plans/{planCode}/profile` | Customer Plans | `getPlanProfile` | Get profile details |
| `PATCH` | `/v1/customer-plans/{planCode}/profile` | Customer Plans | `updatePlan` | Update profile details |
| `GET` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/all` | Customer Plan Tariffs | `getBillingPlanTariffsForAllGroupsByCode` | Get plan tariff details for all charger groups |
| `PUT` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/all` | Customer Plan Tariffs | `updatePlanGroupTariffsByCode_1` | Update plan tariff details for all charger groups |
| `POST` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/all/batch/{id}/add` | Customer Plan Tariffs - Batch | `addChargerGroupAllToBatch` | Add an update action of plan tariff details for all groups for a charger plan to the active batch |
| `POST` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/batch` | Customer Plan Tariffs - Batch | `openBillingPlanTariffsBatch` | Open a batch for open plan tariff details and group for a charger plan |
| `GET` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/batch/{id}` | Customer Plan Tariffs - Batch | `getBillingPlanTariffsBatch` | Get the active batch details for open plan tariff details and group for a charger plan. |
| `POST` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/batch/{id}/execute` | Customer Plan Tariffs - Batch | `executeChargerGroupBatch` | Execute the active batch for updating plan tariff details and group for a charger plan |
| `POST` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/batch/{id}/rollback` | Customer Plan Tariffs - Batch | `rollBackChargerGroupBatch` | Roll back the active batch for updating plan tariff details and group for a charger plan |
| `GET` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/{chargerGroupId}` | Customer Plan Tariffs | `getBillingPlanGroupTariffsByCode` | Get plan tariff details for specific charger group |
| `PUT` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/{chargerGroupId}` | Customer Plan Tariffs | `updatePlanGroupTariffsByCode` | Update plan tariff details for specific charger group |
| `POST` | `/v1/customer-plans/{planCode}/tariffs/charger-groups/{chargerGroupId}/batch/{id}/add` | Customer Plan Tariffs - Batch | `addChargerGroupToBatch` | Add an update action of plan tariff details and group for a charger plan to the active batch |
| `DELETE` | `/v1/customer-plans/{planCode}/tariffs/charger-speed/{chargerSpeed}/charger-groups/all` | Customer Plan Tariffs | `deletePlanGroupTariffsByCodeAndSpeed_1` | Delete plan tariffs for all charger groups with specific charger speed |
| `DELETE` | `/v1/customer-plans/{planCode}/tariffs/charger-speed/{chargerSpeed}/charger-groups/{chargerGroupId}` | Customer Plan Tariffs | `deletePlanGroupTariffsByCodeAndSpeed` | Delete plan tariffs for specific charger group and charger speed |
| `DELETE` | `/v1/customer-plans/{planCode}/tariffs/connector-type/{connectorType}/charger-groups/all` | Customer Plan Tariffs | `deletePlanGroupTariffsByCodeAndConnectorType_1` | Delete plan tariffs for all charger groups with specific connector type |
| `DELETE` | `/v1/customer-plans/{planCode}/tariffs/connector-type/{connectorType}/charger-groups/{chargerGroupId}` | Customer Plan Tariffs | `deletePlanGroupTariffsByCodeAndConnectorType` | Delete plan tariffs for specific charger group and connector type |
| `POST` | `/v1/customer-tariffs` | Customer Tariffs | `addCustomerTariff` | Create customer tariff |
| `POST` | `/v1/customer-tariffs/filter` | Customer Tariffs | `filter_3` | Find customer tariffs |
| `POST` | `/v1/customer-tariffs/schedule/create` | Customer Tariffs | `addCustomerScheduledTariff` | Create customer scheduled tariff |
| `PATCH` | `/v1/customer-tariffs/schedule/delete` | Customer Tariffs | `deleteCustomerTariffScheduling` | Delete billing tariff scheduling |
| `POST` | `/v1/customer-tariffs/schedule/now` | Customer Tariffs | `applyCustomerTariffScheduling` | Apply billing tariff scheduling |
| `GET` | `/v1/customer-tariffs/{id}` | Customer Tariffs | `getCustomerTariff` | Get customer tariff |
| `PATCH` | `/v1/customer-tariffs/{id}` | Customer Tariffs | `updateCustomerTariff` | Update customer tariff |
| `POST` | `/v1/customer-tariffs/{id}/history/filter` | Customer Tariffs | `filter_2` | Find previous customer tariffs |
| `GET` | `/v1/customer-tariffs/{id}/reservations` | Customer Tariffs | `getCustomerReservationTariff` | Get reservation tariff |
| `PATCH` | `/v1/customer-tariffs/{id}/reservations/by-date` | Customer Tariffs | `updateCustomerReservationTariffByDate` | Update future reservation tariff |
| `PATCH` | `/v1/customer-tariffs/{id}/reservations/now` | Customer Tariffs | `updateCustomerReservationTariffNow` | Update immediate reservation tariff |
| `POST` | `/v1/customer-tariffs/{id}/reservations/now/terms` | Customer Tariffs | `createCustomerReservationTariffTerm` | Create immediate reservation tariff terms |
| `DELETE` | `/v1/customer-tariffs/{id}/reservations/now/terms/{termId}` | Customer Tariffs | `deleteCustomerReservationTariffTerm` | Delete immediate reservation tariff terms |
| `PATCH` | `/v1/customer-tariffs/{id}/reservations/now/terms/{termId}` | Customer Tariffs | `updateCustomerReservationTariffTerm` | Update immediate reservation tariff terms |
| `GET` | `/v1/customer-tariffs/{id}/schedule` | Customer Tariffs | `getCustomerTariffScheduling` | Get customer tariff scheduling |
| `PATCH` | `/v1/customer-tariffs/{id}/schedule` | Customer Tariffs | `updateCustomerTariffScheduling` | Update customer tariff scheduling |
| `POST` | `/v1/energy-storage` | Energy Storage | `createEnergyStorage` | Create energy storage configuration |
| `POST` | `/v1/energy-storage/filter` | Energy Storage | `findByFilter` | Filter energy storage configuration |
| `DELETE` | `/v1/energy-storage/{id}` | Energy Storage | `deleteById` | Delete energy storage configuration by id |
| `GET` | `/v1/energy-storage/{id}` | Energy Storage | `getEnergyStorage` | Get energy storage by id |
| `PATCH` | `/v1/energy-storage/{id}` | Energy Storage | `updateById` | Update energy storage configuration by id |
| `PATCH` | `/v1/energy-storage/{id}/actions/status` | Energy Storage | `status` | Update energy storage status by id |
| `POST` | `/v1/ev-transactions/chargers/{identityKey}/filter` | EV Transactions | `filterEvTransactionsByIdentityKey` | Find EV transactions by identity key |
| `POST` | `/v1/ev-transactions/cost-breakdown` | EV Transactions | `getCostBreakdown` | Get ev transactions cost breakdown |
| `POST` | `/v1/ev-transactions/filter` | EV Transactions | `filterEvTransactions` | Find EV transactions |
| `POST` | `/v1/ev-transactions/last` | EV Transactions | `getLastEvTransactions` | Find last EV transactions |
| `POST` | `/v1/ev-transactions/ocpi-cdrs/filter` | EV Transactions | `filterTransactions_1` | Find roaming CDRs |
| `POST` | `/v1/ev-transactions/roaming-shell-cdrs/filter` | Custom Integrations | `filterTransactions` | Find Shell roaming CDRs |
| `GET` | `/v1/ev-transactions/{id}` | EV Transactions | `getEvTransaction` | Get EV transaction details |
| `GET` | `/v1/ev-transactions/{id}/cost` | EV Transactions | `getEvTransactionCost` | Get EV transaction cost |
| `GET` | `/v1/ev-transactions/{id}/cost-breakdown/pdf` | EV Transactions | `getCostBreakdownPdf` | Get ev transaction Cost Breakdown as PDF |
| `GET` | `/v1/fiscalization/invoices/{id}` | Fiscalization | `getFiscalizationData` | Get fiscalization data by invoice id |
| `POST` | `/v1/guest-driver-details/filter` | Guest Driver Details | `getGuestDriverDetails` | Find guest driver details |
| `POST` | `/v1/interface-log/migrate` | Inteface-log | `migrateInterfaceLogData` | Migrate interface-logs by date range |
| `POST` | `/v1/oems` | Oems | `addVehicle_1` | Add OEM |
| `POST` | `/v1/operators` | Operators | `addOperator` | Add operator |
| `POST` | `/v1/operators/filter` | Operators | `filterOperators` | Find operators |
| `DELETE` | `/v1/operators/{id}` | Operators | `deleteOperatorById` | Delete operator |
| `GET` | `/v1/operators/{id}` | Operators | `getOperator` | Find operator |
| `PATCH` | `/v1/operators/{id}` | Operators | `updateOperator` | Update operator |
| `PATCH` | `/v1/operators/{id}/reactivate` | Operators | `reactivate` | Reactivate operator |
| `PATCH` | `/v1/operators/{id}/suspend` | Operators | `suspend` | Suspend operator |
| `PATCH` | `/v1/operators/{id}/unblock` | Operators | `unblockOperator` | Unblock operator |
| `POST` | `/v1/payment-gateway/custom-fields/batch` | Payment Gateway | `batchInsert` | Create batch of custom fields |
| `POST` | `/v1/payment-gateway/custom-fields/filter` | Payment Gateway | `getCustomFieldsByFilter` | Find custom fields |
| `DELETE` | `/v1/payment-gateway/custom-fields/{id}` | Payment Gateway | `deleteCustomField` | Delete custom field |
| `PATCH` | `/v1/payment-gateway/custom-fields/{id}` | Payment Gateway | `updateCustomField` | Update custom field |
| `POST` | `/v1/properties` | Properties | `addProperty` | Create property |
| `POST` | `/v1/properties/batch` | Properties | `addProperties` | Create properties |
| `POST` | `/v1/properties/filter` | Properties | `filterProperties` | Find properties |
| `DELETE` | `/v1/properties/{id}` | Properties | `deletePropertyById` | Delete property |
| `GET` | `/v1/properties/{id}` | Properties | `getProperty` | Find property |
| `PATCH` | `/v1/properties/{id}` | Properties | `updateProperty` | Update property |
| `PATCH` | `/v1/properties/{id}/actions/refresh-runtime-engine` | Properties | `refreshRuntimeEngine_1` | Refresh property engine |
| `DELETE` | `/v1/properties/{id}/energy-policies` | Property Energy Policies | `deletePropertyById_1` | Delete energy policy |
| `GET` | `/v1/properties/{id}/energy-policies` | Property Energy Policies | `getPolicy_1` | Find energy policy |
| `PATCH` | `/v1/properties/{id}/energy-policies` | Property Energy Policies | `updatePolicy_1` | Update energy policy |
| `POST` | `/v1/properties/{id}/energy-policies` | Property Energy Policies | `addPolicy_1` | Add energy policy |
| `PATCH` | `/v1/properties/{id}/external` | Properties | `updateExternalProperty` | Update external property |
| `POST` | `/v1/raw-logs/migrate` | Raw Logs | `migrateRawLogs` | Send raw logs |
| `POST` | `/v1/regulation/nevi/error-codes` | Regulations | `getTransactionsErrorCodes` | (NON-PROD) Find Nevi transactions error codes |
| `POST` | `/v1/regulation/nevi/peak-power` | Regulations | `filterEvTransactionsPeakPower` | (NON-PROD) Find Nevi transactions peak kW |
| `POST` | `/v1/regulation/nevi/status-change-history` | Regulations | `findStatusChangeHistory` | (NON-PROD) Find Nevi charger status change history |
| `POST` | `/v1/reservations/filter` | Reservations | `filterReservations` | Find reservations |
| `GET` | `/v1/reservations/{id}` | Reservations | `getReservation` | Get reservation details |
| `POST` | `/v1/resources` | Resources | `uploadFiles` | Upload files |
| `POST` | `/v1/site-map/accounts/{accountNumber}/chargers` | Site Map | `getChargersDataForAccount` | Retrieve multiple chargers data |
| `GET` | `/v1/site-map/accounts/{accountNumber}/chargers/{chargerId}` | Site Map | `getSingleChargerDataForAccount` | Retrieve single station site map data |
| `POST` | `/v1/site-map/accounts/{accountNumber}/cluster` | Site Map | `getSiteClustersForAccount` | Retrieve site map clusters |
| `POST` | `/v1/site-map/accounts/{accountNumber}/sites` | Site Map | `getSitesDataForAccount` | Retrieve site map clusters |
| `POST` | `/v1/site-map/anonymous/chargers` | Site Map | `getChargersDataForAnonymous` | Retrieve site map clusters |
| `GET` | `/v1/site-map/anonymous/chargers/{chargerId}` | Site Map | `getSingleChargerDataForAnonymous` | Retrieve single station site map data |
| `POST` | `/v1/site-map/anonymous/cluster` | Site Map | `getSiteClustersForAnonymous` | Retrieve site map clusters |
| `POST` | `/v1/site-map/anonymous/sites` | Site Map | `getSitesDataForAnonymous` | Retrieve site map clusters |
| `POST` | `/v1/sites` | Sites | `addSite` | Create site |
| `POST` | `/v1/sites/batch` | Sites | `addSites` | Create sites |
| `POST` | `/v1/sites/filter` | Sites | `filterSites` | Find sites |
| `POST` | `/v1/sites/history/charger/filter` | Sites | `filterSiteChargersHistory` | Get chargers update site history by filter |
| `POST` | `/v1/sites/history/filter` | Sites | `filterSitesHistory` | Get site history by filter |
| `POST` | `/v1/sites/search` | Sites | `searchSites` | Search sites |
| `POST` | `/v1/sites/vehicles-schedule/enrich` | Sites | `enrichScheduleRecords` | Enrich vehicles schedule records |
| `DELETE` | `/v1/sites/{id}` | Sites | `deleteSiteById_1` | Delete site |
| `GET` | `/v1/sites/{id}` | Sites | `getSite` | Find site |
| `PATCH` | `/v1/sites/{id}` | Sites | `updateSite` | Update site |
| `PATCH` | `/v1/sites/{id}/actions/refresh-runtime-engine` | Sites | `refreshRuntimeEngine` | Refresh site engine |
| `DELETE` | `/v1/sites/{id}/energy-policies` | Site Energy Policies | `deleteSiteEnergyPolicyBySiteId` | Delete energy policy |
| `GET` | `/v1/sites/{id}/energy-policies` | Site Energy Policies | `getPolicy` | Find energy policy |
| `PATCH` | `/v1/sites/{id}/energy-policies` | Site Energy Policies | `updatePolicy` | Update energy policy |
| `POST` | `/v1/sites/{id}/energy-policies` | Site Energy Policies | `addPolicy` | Add energy policy |
| `GET` | `/v1/sites/{id}/evses/{evseId}/allowed` | Chargers Compound | `validateEvseReplacement` | Validate EVSE id for charger replacement in a site |
| `PATCH` | `/v1/sites/{id}/external` | Sites | `updateExternalSite` | Update external site |
| `POST` | `/v1/sites/{id}/history/override-records/filter` | Sites | `getSiteHistoryOverrideRecords` | Get site history override records |
| `PATCH` | `/v1/sites/{id}/history/{historyId}/override` | Sites | `updateHistory` | Update date of site history record |
| `DELETE` | `/v1/sites/{id}/resources/{resourceId}` | Sites | `deleteSiteResource` | Delete resource |
| `GET` | `/v1/sites/{id}/resources/{resourceId}` | Sites | `findSiteResource` | Get resource |
| `PATCH` | `/v1/sites/{id}/resources/{resourceId}` | Sites | `updateSiteResource` | Update resource |
| `POST` | `/v1/sites/{id}/resources/{resourceId}` | Sites | `addResourceToSite` | Add resource |
| `POST` | `/v1/sites/{id}/schedules/import` | Sites | `loadVehiclesSchedule` | Add vehicles schedule to a given site by a CSV file |
| `GET` | `/v1/sites/{id}/summary` | Sites | `getSiteSummary` | Get site history summary |
| `POST` | `/v1/sites/{siteId}/actions/calculate-planning` | Sites | `calculatePlanning` | calculate planning |
| `POST` | `/v1/sites/{siteId}/actions/cancel-reservation` | Sites | `cancelReservation` | cancel reservation |
| `POST` | `/v1/sites/{siteId}/actions/schedule` | Sites | `saveSchedule` | saving schedule |
| `POST` | `/v1/sites/{siteId}/energy-planning/calculate` | Grid Management | `calcEnergyPlanning` | Calculate energy planning |
| `PATCH` | `/v1/sites/{siteId}/energy-planning/calculate-planning-update` | Grid Management | `calculateEnergyPlanningForUpdate` | Calculate energy planning for update |
| `POST` | `/v1/sites/{siteId}/energy-planning/calculate-simulation` | Grid Management | `simulateEnergyPlanningCalculation` | Calculate energy planning simulation |
| `PATCH` | `/v1/sites/{siteId}/energy-planning/calculate-simulation-for-update` | Grid Management | `simulateEnergyPlanningCalculationForUpdate` | Calculate energy planning simulation for update |
| `GET` | `/v1/sites/{siteId}/energy-planning/result` | Grid Management | `getLastEnergyPlanningResult` | Get last energy planning result |
| `POST` | `/v1/sites/{siteId}/schedule/actions/simulate-validation` | Sites | `validateScheduleForSimulation` | validating schedule for simulation |
| `POST` | `/v1/sites/{siteId}/schedule/actions/validate` | Sites | `validateSchedule` | validating schedule |
| `POST` | `/v1/sites/{siteId}/schedule/actions/validate-csv` | Sites | `validateCsvSchedule` | validating schedule |
| `PATCH` | `/v1/sites/{siteId}/schedule/{scheduleId}/actions/validate-for-update` | Sites | `validateScheduleUpdate` | validating schedule for update planning |
| `POST` | `/v1/soc-data` | SOC Data | `submitSocData` | Submit SOC data |
| `GET` | `/v1/topologies` | Topologies | `getTopologies` | Get all topologies |
| `POST` | `/v1/topologies` | Topologies | `createTopology` | Create topology |
| `POST` | `/v1/topologies/simple` | Topologies | `createSimpleTopology` | Create simple topology |
| `DELETE` | `/v1/topologies/{id}` | Topologies | `deleteTopology` | Delete topology |
| `GET` | `/v1/topologies/{id}` | Topologies | `getTopology` | Get topology details |
| `PUT` | `/v1/topologies/{id}` | Topologies | `updateTopology` | Update topology |
| `PATCH` | `/v1/user-notifications-preferences/{userId}` | User Notification Preferences | `updateNotificationPreferences` | Update notification preferences |
| `POST` | `/v1/utility-tariffs` | Utility Tariffs | `createUtilityTariff` | Create utility tariff |
| `POST` | `/v1/utility-tariffs/filter` | Utility Tariffs | `filter_1` | Find utility tariffs |
| `PATCH` | `/v1/utility-tariffs/time-ranges` | Utility Tariffs | `updateUtilityTariffTimeRanges` | Update utility tariff time ranges |
| `POST` | `/v1/utility-tariffs/time-ranges` | Utility Tariffs | `createUtilityTariffTimeRanges` | Create utility tariff time ranges |
| `POST` | `/v1/utility-tariffs/time-ranges/filter` | Utility Tariffs | `filter` | Find utility tariffs time ranges by filter |
| `DELETE` | `/v1/utility-tariffs/{id}` | Utility Tariffs | `deleteUtilityTariffById` | Delete utility tariff |
| `GET` | `/v1/utility-tariffs/{id}` | Utility Tariffs | `getUtilityTariff` | Get utility tariff |
| `PATCH` | `/v1/utility-tariffs/{id}` | Utility Tariffs | `updateUtilityTariff` | Update utility tariff |
| `PATCH` | `/v1/utility-tariffs/{id}/time-ranges` | Utility Tariffs | `deleteUtilityTariffTimeRanges` | Delete utility tariff time ranges |
| `POST` | `/v1/vdas` | VDA | `create` | Create a vda |
| `POST` | `/v1/vdas-attachment` | VDA-Attachment | `create_1` | Create a vda attachment |
| `POST` | `/v1/vdas-attachment/delete` | VDA-Attachment | `delete_1` | Delete vda attachments by ids |
| `POST` | `/v1/vdas-attachment/filter` | VDA-Attachment | `filterVdaAttachment` | Find vdas by vda attachment properties |
| `DELETE` | `/v1/vdas-attachment/{id}` | VDA-Attachment | `deleteVdaAttachment` | Delete vda attachment by id |
| `PATCH` | `/v1/vdas-attachment/{id}` | VDA-Attachment | `update` | Update a vda attachment |
| `POST` | `/v1/vdas/delete` | VDA | `delete` | Delete vdas by ids |
| `POST` | `/v1/vdas/filter` | VDA | `filterVda` | Find vdas |
| `DELETE` | `/v1/vdas/{id}` | VDA | `deleteSiteById` | Delete a vda |
| `GET` | `/v1/vdas/{id}` | VDA | `getVda` | Find vda |
| `POST` | `/v1/vehicle-manufacturers` | Vehicle Manufacturers | `createVehicleManufacturer` | Add vehicle manufacturer |
| `POST` | `/v1/vehicle-manufacturers/filter` | Vehicle Manufacturers | `filterVehicleManufacturer` | Find vehicle manufacturers |
| `DELETE` | `/v1/vehicle-manufacturers/{id}` | Vehicle Manufacturers | `deleteVehicleManufacturerById` | Delete vehicle manufacturer |
| `GET` | `/v1/vehicle-manufacturers/{id}` | Vehicle Manufacturers | `getVehicleManufacturerById` | Get vehicle manufacturer |
| `PATCH` | `/v1/vehicle-manufacturers/{id}` | Vehicle Manufacturers | `updateVehicleManufacturer` | Update vehicle manufacturer |
| `POST` | `/v1/vehicle-models` | Vehicle Models | `addVehicleModel` | Add vehicle model |
| `POST` | `/v1/vehicle-models/filter` | Vehicle Models | `filterVehicleModel` | Finds vehicle models |
| `DELETE` | `/v1/vehicle-models/{id}` | Vehicle Models | `deleteVehicleModelById` | Delete vehicle model |
| `GET` | `/v1/vehicle-models/{id}` | Vehicle Models | `getVehicleModelById` | Get vehicle model |
| `PATCH` | `/v1/vehicle-models/{id}` | Vehicle Models | `updateVehicleModel` | Update vehicle model |
| `POST` | `/v1/vehicle/vid-block-list` | VIDs | `updateBlockedVidNumbers` | Update blocked VID numbers |
| `GET` | `/v1/vehicle/vid-block-list/filter` | VIDs | `filterBlockedVidNumbers` | Filter blocked VID numbers |
| `POST` | `/v1/vehicles` | Vehicles | `addVehicle` | Add vehicle |
| `POST` | `/v1/vehicles/filter` | Vehicles | `getVehiclesByFilter` | Find vehicles |
| `DELETE` | `/v1/vehicles/{id}` | Vehicles | `deleteVehicleById` | Delete vehicle |
| `GET` | `/v1/vehicles/{id}` | Vehicles | `getVehicleById` | Get vehicle |
| `PATCH` | `/v1/vehicles/{id}` | Vehicles | `updateVehicle` | Update vehicle |
| `GET` | `/v2/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility` | Customer Plans Eligibility | `getPlanEligibilityByCountryCurrency` | Get a customer plan eligibility by plan code and country-currency |
| `PATCH` | `/v2/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility` | Customer Plans Eligibility | `updatePlanEligibilityByCountryCurrency` | Update a customer plan eligibility by plan code and country-currency |
| `PATCH` | `/v2/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/disable` | Customer Plans Eligibility | `disablePlanEligibilityByCountryCurrency` | Disable customer plan eligibility by plan code and country-currency |
| `PATCH` | `/v2/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/enable` | Customer Plans Eligibility | `enablePlanEligibilityByCountryCurrency` | Enable customer plan eligibility by plan code and country-currency |
| `GET` | `/v2/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/identifiers` | Customer Plans Eligibility Identifiers | `getIdentifiersByCountryCurrency` | Get eligibility identifiers by plan code and country-currency with pagination |
| `PATCH` | `/v2/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/identifiers` | Customer Plans Eligibility Identifiers | `addPlanEligibilityIdentifiersByCountryCurrency` | Add identifiers to a customer plan eligibility by plan code and country-currency |
| `DELETE` | `/v2/customer-plans/{planCode}/country-currency/{countryCurrency}/locales/{locale}/eligibility/identifiers/{identifierId}` | Customer Plans Eligibility Identifiers | `deletePlanEligibilityIdentifierByCountryCurrency` | Delete an identifier from plan eligibility by plan code and country-currency |
| `GET` | `/v2/customer-plans/{planCode}/locales/{locale}/eligibility` | Customer Plans Eligibility | `getPlanEligibility` | Get a customer plan eligibility by plan code |
| `PATCH` | `/v2/customer-plans/{planCode}/locales/{locale}/eligibility` | Customer Plans Eligibility | `updatePlanEligibility` | Update a customer plan eligibility by plan code |
| `PATCH` | `/v2/customer-plans/{planCode}/locales/{locale}/eligibility/disable` | Customer Plans Eligibility | `disablePlanEligibility` | Disable customer plan eligibility |
| `PATCH` | `/v2/customer-plans/{planCode}/locales/{locale}/eligibility/enable` | Customer Plans Eligibility | `enablePlanEligibility` | Enable customer plan eligibility |
| `GET` | `/v2/customer-plans/{planCode}/locales/{locale}/eligibility/identifiers` | Customer Plans Eligibility Identifiers | `getIdentifiers` | Get eligibility identifiers by plan code with pagination |
| `PATCH` | `/v2/customer-plans/{planCode}/locales/{locale}/eligibility/identifiers` | Customer Plans Eligibility Identifiers | `addPlanEligibilityIdentifiers` | Add identifiers to a customer plan eligibility by plan code |
| `DELETE` | `/v2/customer-plans/{planCode}/locales/{locale}/eligibility/identifiers/{identifierId}` | Customer Plans Eligibility Identifiers | `deletePlanEligibilityIdentifier` | Delete an identifier from plan eligibility by plan code |

## Customers

| Method | Path | Tags | Operation ID | Summary |
| --- | --- | --- | --- | --- |
| `PATCH` | `/customers/v1/reservations/{id}/cancel` | Reservations | `cancelReservation` | Cancel reservation by id |
