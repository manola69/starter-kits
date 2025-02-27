import forta_agent
from forta_agent import Finding, FindingType, FindingSeverity, get_json_rpc_url, EntityType
from src.constants import THRESHOLDS, DAY_LOOKBACK_WINDOW
from web3 import Web3

web3 = Web3(Web3.HTTPProvider(get_json_rpc_url()))
CHAIN_ID = -1
ALERT_COUNT = 0  # stats to emit anomaly score
DENOMINATOR_COUNT = 0  # stats to emit anomaly score

def initialize():
    """
    this function initializes the state variables that are tracked across tx and blocks
    it is called from test to reset state between tests
    """
    global ALERT_COUNT
    ALERT_COUNT = 0

    global DENOMINATOR_COUNT
    DENOMINATOR_COUNT = 0


def detect_suspicious_native_transfers(w3, transaction_event: forta_agent.transaction_event.TransactionEvent) -> list:
    findings = []
    global CHAIN_ID
    global ALERT_COUNT
    global DENOMINATOR_COUNT
    if CHAIN_ID == -1:
        CHAIN_ID = w3.eth.chainId

    # filter the transaction logs for any Tether transfers
    value = transaction_event.transaction.value
    if value > 0:
        DENOMINATOR_COUNT += 1

    if value >= THRESHOLDS[CHAIN_ID][1]:
        to = transaction_event.to
        from_ = transaction_event.from_

        block_number = transaction_event.block_number
        BLOCK_TIME = 15  # seconds
        older_block_number = block_number - (24 * 60 * 60 * DAY_LOOKBACK_WINDOW)//BLOCK_TIME
        older_value = w3.eth.get_balance(Web3.toChecksumAddress(from_), block_identifier=older_block_number)
        current_value = w3.eth.get_balance(Web3.toChecksumAddress(from_), block_identifier=block_number)

        if older_value < THRESHOLDS[CHAIN_ID][0]:
            ALERT_COUNT += 1

            anomaly_score = (ALERT_COUNT * 1.0) / DENOMINATOR_COUNT
            
            labels = [{"entity": from_,
                   "entity_type": EntityType.Address,
                   "label": "attacker",
                   "confidence": 0.3}]

            findings.append(Finding({
                'name': 'Large Native Transfer Out',
                'description': f'High amount of native tokens transferred: {value}',
                'alert_id': 'LARGE-TRANSFER-OUT',
                'severity': FindingSeverity.Low,
                'type': FindingType.Info,
                'metadata': {
                    'anomaly_score': anomaly_score,
                    'to': to,
                    'from': from_,
                    'current_block': block_number,
                    'balance_at_current_block': current_value,
                    'balance_at_older_block': older_value,
                    'older_block': older_block_number,
                    'transfer_value': value
                },
                'labels': labels
            }))

    return findings


def provide_handle_transaction(w3):
    def handle_transaction(transaction_event: forta_agent.transaction_event.TransactionEvent) -> list:
        return detect_suspicious_native_transfers(w3, transaction_event)

    return handle_transaction


real_handle_transaction = provide_handle_transaction(web3)


def handle_transaction(transaction_event: forta_agent.transaction_event.TransactionEvent):
    return real_handle_transaction(transaction_event)
