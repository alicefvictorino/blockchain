import json
import hashlib
import time


GENESIS_TIMESTAMP = 0
GENESIS_PREVIOUS_HASH = "0" * 64


# ============================================================
# BLOCO
# ============================================================

class Block:
    def __init__(self, index, transactions, previous_hash, difficulty, timestamp=None):
        self.index = index
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = 0
        self.difficulty = difficulty
        self.hash = self.mine_block()

    def calculate_hash(self):
        """Gera o SHA-256 do conteúdo do bloco."""
        block_string = json.dumps({
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "nonce": self.nonce,
            "difficulty": self.difficulty 
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(block_string).hexdigest()

    def mine_block(self):
        """Executa o Proof of Work"""
        target = "0" * self.difficulty
        while True:
            current_hash = self.calculate_hash()
            if current_hash.startswith(target):
                print(f" Bloco {self.index} minerado! Nonce: {self.nonce} | Hash: {current_hash[:20]}...")
                return current_hash
            self.nonce += 1

    def get_work(self):
        """
        Trabalho deste bloco = 2^difficulty.
        Quanto maior a dificuldade, mais trabalho foi necessário.
        Usado na regra de consenso: vence a cadeia com MAIOR trabalho acumulado.
        """
        return 2 ** self.difficulty

    def to_dict(self):
        """Serializa o bloco para JSON (uso na API e no Kafka da Pessoa 2)."""
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, data):
        """
        Reconstrói um bloco a partir de dicionário recebido pela rede.
        NÃO minera de novo — apenas restaura o estado salvo.
        Usado quando é entregue um bloco via Kafka.
        """
        block = cls.__new__(cls)
        block.index = data["index"]
        block.timestamp = data["timestamp"]
        block.transactions = data["transactions"]
        block.previous_hash = data["previous_hash"]
        block.nonce = data["nonce"]
        block.difficulty = data["difficulty"]
        block.hash = data["hash"]
        return block


# ============================================================
# BLOCKCHAIN
# ============================================================

class Blockchain:
    def __init__(self, difficulty=4, transaction_validator=None):
        self.difficulty = difficulty
        self.transaction_validator = transaction_validator
        # chain principal
        self.chain = []
        # forks conhecidos: dict { hash_do_bloco_raiz: [lista de blocos alternativos] }
        self.forks = {}
        # ramos alternativos por hash do ultimo bloco do ramo
        self.fork_branches = {}
        self.create_genesis_block()

    # ----------------------------------------------------------
    # Bloco gênese
    # ----------------------------------------------------------

    def create_genesis_block(self):
        """Cria o primeiro bloco da rede."""
        print("Criando bloco gênese...")
        genesis = Block(
            index=0,
            transactions=[{"type": "genesis", "data": "Início da Votação"}],
            previous_hash=GENESIS_PREVIOUS_HASH,
            difficulty=self.difficulty,
            timestamp=GENESIS_TIMESTAMP
        )
        self.chain.append(genesis)

    # ----------------------------------------------------------
    # Consultas básicas
    # ----------------------------------------------------------

    def get_latest_block(self):
        if not self.chain:
            raise RuntimeError("A blockchain está vazia.")
        return self.chain[-1]

    def get_total_work(self, chain=None):
        """
        Calcula o trabalho acumulado de uma cadeia.
        Se nenhuma cadeia for passada, usa a cadeia local.
        Trabalho total = soma de 2^difficulty de cada bloco.
        """
        chain = chain if chain is not None else self.chain
        return sum(block.get_work() for block in chain)

    def get_confirmed_nullifiers(self, chain=None):
        """Retorna os nullifiers ja confirmados na cadeia informada."""
        chain = chain if chain is not None else self.chain
        nullifiers = set()
        for block in chain:
            for transaction in block.transactions:
                nullifier = transaction.get("nullifier")
                if nullifier:
                    nullifiers.add(nullifier)
        return nullifiers

    def get_confirmed_tx_ids(self, chain=None):
        """Retorna os tx_ids ja confirmados na cadeia informada."""
        chain = chain if chain is not None else self.chain
        tx_ids = set()
        for block in chain:
            for transaction in block.transactions:
                tx_id = transaction.get("tx_id")
                if tx_id:
                    tx_ids.add(tx_id)
        return tx_ids

    # ----------------------------------------------------------
    # Adicionar bloco (mineração local)
    # ----------------------------------------------------------

    def add_block(self, transactions):
        """Minera e adiciona um novo bloco à cadeia local."""
        if not isinstance(transactions, list):
            raise TypeError("Transações devem ser uma lista.")
        valid, reason = self._are_transactions_valid(
            transactions,
            confirmed_tx_ids=self.get_confirmed_tx_ids(),
            confirmed_nullifiers=self.get_confirmed_nullifiers(),
        )
        if not valid:
            raise ValueError(f"Transações inválidas: {reason}")

        print(f" Minerando bloco {len(self.chain)}...")
        new_block = Block(
            index=len(self.chain),
            transactions=transactions,
            previous_hash=self.get_latest_block().hash,
            difficulty=self.difficulty
        )
        self.chain.append(new_block)
        return new_block   # Pessoa 2 pode publicar este bloco no Kafka

    def _is_genesis_transaction(self, transaction):
        return isinstance(transaction, dict) and transaction.get("type") == "genesis"

    def _are_transactions_valid(
        self,
        transactions,
        confirmed_tx_ids=None,
        confirmed_nullifiers=None,
    ):
        seen_tx_ids = set()
        seen_nullifiers = set()
        confirmed_tx_ids = confirmed_tx_ids or set()
        confirmed_nullifiers = confirmed_nullifiers or set()

        for transaction in transactions:
            if self._is_genesis_transaction(transaction):
                continue
            if not isinstance(transaction, dict):
                return False, "Transação deve ser um dicionário"

            tx_id = transaction.get("tx_id")
            nullifier = transaction.get("nullifier")

            if not tx_id:
                return False, "Transação sem tx_id"
            if not nullifier:
                return False, "Transação sem nullifier"
            if tx_id in seen_tx_ids or tx_id in confirmed_tx_ids:
                return False, f"tx_id duplicado: {tx_id}"
            if nullifier in seen_nullifiers or nullifier in confirmed_nullifiers:
                return False, f"nullifier duplicado: {nullifier}"

            if self.transaction_validator is not None:
                valid, reason = self.transaction_validator(transaction)
                if not valid:
                    return False, reason

            seen_tx_ids.add(tx_id)
            seen_nullifiers.add(nullifier)

        return True, "OK"

    # ----------------------------------------------------------
    # Validação
    # ----------------------------------------------------------

    def is_valid_block(
        self,
        block,
        expected_previous_hash,
        confirmed_tx_ids=None,
        confirmed_nullifiers=None,
    ):
        """
        Valida um bloco individual recebido da rede.
        Verifica:
          1. Hash interno correto (integridade)
          2. Encadeamento correto com o bloco anterior
          3. Proof of Work satisfeito
        """
        # 1. Hash interno
        if block.hash != block.calculate_hash():
            return False, "Hash do bloco inválido"

        # 2. Encadeamento
        if block.previous_hash != expected_previous_hash:
            return False, "Hash anterior não corresponde"

        # 3. Proof of Work
        if not block.hash.startswith("0" * block.difficulty):
            return False, "Proof of Work inválido"

        if confirmed_tx_ids is None or confirmed_nullifiers is None:
            confirmed_tx_ids, confirmed_nullifiers = self._confirmed_before_hash(
                expected_previous_hash
            )
        valid_transactions, reason = self._are_transactions_valid(
            block.transactions,
            confirmed_tx_ids=confirmed_tx_ids,
            confirmed_nullifiers=confirmed_nullifiers,
        )
        if not valid_transactions:
            return False, reason

        return True, "OK"

    def _confirmed_before_hash(self, previous_hash):
        tx_ids = set()
        nullifiers = set()

        for block in self.chain:
            for transaction in block.transactions:
                if self._is_genesis_transaction(transaction):
                    continue
                tx_id = transaction.get("tx_id")
                nullifier = transaction.get("nullifier")
                if tx_id:
                    tx_ids.add(tx_id)
                if nullifier:
                    nullifiers.add(nullifier)
            if block.hash == previous_hash:
                break

        return tx_ids, nullifiers

    def _confirmed_sets_from_chain(self, chain):
        tx_ids = set()
        nullifiers = set()
        for block in chain:
            for transaction in block.transactions:
                if self._is_genesis_transaction(transaction):
                    continue
                tx_id = transaction.get("tx_id")
                nullifier = transaction.get("nullifier")
                if tx_id:
                    tx_ids.add(tx_id)
                if nullifier:
                    nullifiers.add(nullifier)
        return tx_ids, nullifiers

    def _registrar_branch_visualizacao(self, fork_point_hash, divergence_index, branch):
        if fork_point_hash not in self.forks:
            self.forks[fork_point_hash] = []
        self.forks[fork_point_hash].append({
            "divergence_index": divergence_index,
            "discarded_branch": [b.to_dict() for b in branch],
            "work": self.get_total_work(branch)
        })

    def is_chain_valid(self, chain=None):
        """
        Valida a integridade de uma cadeia completa.
        Pode validar a cadeia local ou uma cadeia externa recebida da rede.
        """
        chain = chain if chain is not None else self.chain

        if not chain:
            return False

        # Valida bloco gênese
        genesis = chain[0]
        if genesis.hash != genesis.calculate_hash():
            print(" Bloco gênese corrompido!")
            return False
        if not genesis.hash.startswith("0" * genesis.difficulty):
            print(" PoW do bloco gênese inválido!")
            return False

        # Valida os demais blocos
        confirmed_tx_ids = set()
        confirmed_nullifiers = set()
        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]

            valid, reason = self.is_valid_block(
                current,
                previous.hash,
                confirmed_tx_ids=confirmed_tx_ids,
                confirmed_nullifiers=confirmed_nullifiers,
            )
            if not valid:
                print(f" Bloco {i} inválido: {reason}")
                return False

            for transaction in current.transactions:
                if self._is_genesis_transaction(transaction):
                    continue
                confirmed_tx_ids.add(transaction.get("tx_id"))
                confirmed_nullifiers.add(transaction.get("nullifier"))

        return True

    # ----------------------------------------------------------
    # CONSENSO — regra da cadeia com maior trabalho acumulado
    # ----------------------------------------------------------

    def resolve_consensus(self, received_chain_dicts):
        """
        Recebe uma cadeia externa (lista de dicionários) vinda da rede e aplica a regra de consenso:

        Adota a cadeia com MAIOR TRABALHO ACUMULADO (não apenas a mais longa).

        Retorna True se a cadeia local foi substituída, False caso contrário.
        """
        # Reconstrói os blocos a partir dos dicionários recebidos
        received_chain = [Block.from_dict(b) for b in received_chain_dicts]

        # Valida a cadeia recebida antes de qualquer comparação
        if not self.is_chain_valid(received_chain):
            print("Cadeia recebida é inválida.")
            return False

        work_local    = self.get_total_work(self.chain)
        work_received = self.get_total_work(received_chain)

        print(f"\n Consenso:")
        print(f"   Trabalho local:    {work_local}")
        print(f"   Trabalho recebido: {work_received}")

        if work_received > work_local:
            # Detecta fork antes de substituir
            self._register_fork(self.chain, received_chain)
            self.chain = received_chain
            print("Cadeia substituída pela recebida (maior trabalho).")
            return True
        else:
            print("Cadeia local mantida (trabalho igual ou maior).")
            return False

    # ----------------------------------------------------------
    # FORKS — registro e detecção
    # ----------------------------------------------------------

    def _register_fork(self, old_chain, new_chain):
        """
        Detecta o ponto de divergência entre a cadeia antiga e a nova
        e registra o fork para fins de visualização (Pessoa 2).

        Um fork ocorre quando dois blocos diferentes têm o mesmo previous_hash,
        ou seja, foram minerados a partir do mesmo pai — mineração simultânea.
        """
        # Encontra o ponto de divergência
        divergence_index = 0
        min_len = min(len(old_chain), len(new_chain))

        for i in range(min_len):
            if old_chain[i].hash != new_chain[i].hash:
                divergence_index = i
                break
        else:
            divergence_index = min_len

        if divergence_index == 0:
            return  # Cadeias idênticas até o fim — não é fork

        fork_point_hash = old_chain[divergence_index - 1].hash

        if fork_point_hash not in self.forks:
            self.forks[fork_point_hash] = []

        # Salva a cadeia descartada como fork
        discarded_branch = [b.to_dict() for b in old_chain[divergence_index:]]
        self.forks[fork_point_hash].append({
            "divergence_index": divergence_index,
            "discarded_branch": discarded_branch,
            "work": self.get_total_work(old_chain)
        })

        print(f"\nFork registrado no bloco {divergence_index - 1} "
              f"(hash: {fork_point_hash[:16]}...)")
        print(f"   Ramo descartado tem {len(discarded_branch)} bloco(s).")

    def receive_block(self, block_dict):
        """
        Recebe um bloco individual da rede (via Kafka).
        Se o bloco se encadeia com o topo atual: adiciona normalmente.
        Se cria um fork: registra e decide pelo trabalho acumulado.

        Retorna: 'added' | 'fork_registered' | 'invalid'
        """
        block = Block.from_dict(block_dict)
        latest = self.get_latest_block()

        if any(existing.hash == block.hash for existing in self.chain):
            print("Bloco recebido já existe na cadeia local.")
            return "duplicate"
        if block.hash in self.fork_branches:
            print("Bloco recebido já existe em um fork conhecido.")
            return "duplicate"

        # Caso 1: bloco se encadeia normalmente
        if block.previous_hash == latest.hash:
            valid, reason = self.is_valid_block(block, latest.hash)
            if not valid:
                print(f"Bloco recebido inválido: {reason}")
                return "invalid"
            self.chain.append(block)
            print(f"Bloco {block.index} adicionado via rede.")
            return "added"

        # Caso 2: bloco estende um fork conhecido
        for fork_tip_hash, branch in list(self.fork_branches.items()):
            if block.previous_hash == fork_tip_hash:
                confirmed_tx_ids, confirmed_nullifiers = self._confirmed_sets_from_chain(branch)
                valid, reason = self.is_valid_block(
                    block,
                    fork_tip_hash,
                    confirmed_tx_ids=confirmed_tx_ids,
                    confirmed_nullifiers=confirmed_nullifiers,
                )
                if not valid:
                    print(f"Bloco de fork inválido: {reason}")
                    return "invalid"

                new_branch = branch + [block]
                self.fork_branches.pop(fork_tip_hash, None)
                self.fork_branches[block.hash] = new_branch

                if self.get_total_work(new_branch) > self.get_total_work(self.chain):
                    self._register_fork(self.chain, new_branch)
                    self.chain = new_branch
                    print("Fork adotado por maior trabalho acumulado.")
                    return "chain_replaced"

                print("Fork estendido, mas cadeia principal mantida.")
                return "fork_registered"

        # Caso 3: fork — bloco se encadeia em algum ponto anterior
        for i, existing in enumerate(self.chain):
            if block.previous_hash == existing.hash and i < len(self.chain) - 1:
                valid, reason = self.is_valid_block(block, existing.hash)
                if not valid:
                    print(f"Bloco de fork inválido: {reason}")
                    return "invalid"
                branch = self.chain[:i + 1] + [block]
                self.fork_branches[block.hash] = branch
                self._registrar_branch_visualizacao(existing.hash, i + 1, [block])

                if self.get_total_work(branch) > self.get_total_work(self.chain):
                    self._register_fork(self.chain, branch)
                    self.chain = branch
                    print("Fork adotado por maior trabalho acumulado.")
                    return "chain_replaced"

                print(f"Fork detectado no bloco {i}. Bloco alternativo registrado.")
                return "fork_registered"

        print("Bloco recebido não se encadeia com nenhum bloco conhecido.")
        return "invalid"

    def get_forks_summary(self):
        """
        Retorna um resumo dos forks para a Pessoa 2 exibir na visualização.
        """
        summary = []
        for fork_point, branches in self.forks.items():
            for branch in branches:
                summary.append({
                    "fork_point_hash": fork_point,
                    "divergence_index": branch["divergence_index"],
                    "branch_length": len(branch["discarded_branch"]),
                    "branch_work": branch["work"]
                })
        return summary

    def to_dict(self):
        """Serializa a cadeia inteira (para transmitir via Kafka)."""
        return [block.to_dict() for block in self.chain]


# ============================================================
# DEMONSTRAÇÃO
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  BLOCKCHAIN DE VOTAÇÃO")
    print("=" * 60)

    # --- Nó A: cria a blockchain ---
    print("\nNó A iniciando...\n")
    no_a = Blockchain(difficulty=3)

    no_a.add_block([
        {"voter_id": "abc123", "candidate": "Candidato A"},
        {"voter_id": "def456", "candidate": "Candidato B"},
    ])
    no_a.add_block([
        {"voter_id": "ghi789", "candidate": "Candidato A"},
    ])

    print(f"\nCadeia do Nó A válida? {no_a.is_chain_valid()}")
    print(f"Trabalho acumulado do Nó A: {no_a.get_total_work()}")

    # --- Nó B: cria uma cadeia alternativa (simula fork por mineração simultânea) ---
    print("\n" + "=" * 60)
    print("  Simulando fork: Nó B minera cadeia alternativa...")
    print("=" * 60 + "\n")

    no_b = Blockchain(difficulty=3)
    no_b.add_block([
        {"voter_id": "abc123", "candidate": "Candidato C"},  # voto diferente!
    ])
    no_b.add_block([
        {"voter_id": "def456", "candidate": "Candidato A"},
    ])
    no_b.add_block([
        {"voter_id": "zzz999", "candidate": "Candidato B"},
    ])

    print(f"\nTrabalho acumulado do Nó B: {no_b.get_total_work()}")

    # --- Nó A recebe cadeia do Nó B e aplica consenso ---
    print("\n" + "=" * 60)
    print("  Nó A recebe cadeia do Nó B → aplicando consenso...")
    print("=" * 60)

    substituiu = no_a.resolve_consensus(no_b.to_dict())

    print(f"\nCadeia adotada pelo Nó A tem {len(no_a.chain)} bloco(s).")
    print(f"Cadeia válida após consenso? {no_a.is_chain_valid()}")

    # --- Exibe forks registrados ---
    forks = no_a.get_forks_summary()
    if forks:
        print(f"\nForks registrados: {len(forks)}")
        for f in forks:
            print(f"   Fork no bloco {f['divergence_index'] - 1} | "
                  f"Ramo descartado: {f['branch_length']} bloco(s) | "
                  f"Trabalho: {f['branch_work']}")
    else:
        print("\nNenhum fork registrado.")

    # --- Simula recebimento de bloco individual via rede ---
    print("\n" + "=" * 60)
    print("  Simulando recebimento de bloco individual (via Kafka)...")
    print("=" * 60 + "\n")

    novo_bloco_dict = Block(
        index=len(no_a.chain),
        transactions=[{"voter_id": "new001", "candidate": "Candidato A"}],
        previous_hash=no_a.get_latest_block().hash,
        difficulty=3
    ).to_dict()

    resultado = no_a.receive_block(novo_bloco_dict)
    print(f"Resultado: {resultado}")
    print(f"\nCadeia final do Nó A: {len(no_a.chain)} blocos")
    print(f"Válida? {no_a.is_chain_valid()}")
