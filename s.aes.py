import sys
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox,
                             QGroupBox, QMessageBox, QTabWidget)

# S盒与逆S盒（遵循文档表D.1）
S_BOX = [
    [0x9, 0x4, 0xA, 0xB],
    [0xD, 0x1, 0x8, 0x5],
    [0x6, 0x2, 0x0, 0x3],
    [0xC, 0xE, 0xF, 0x7]
]

INV_S_BOX = [
    [0xA, 0x5, 0x9, 0xB],
    [0x1, 0x7, 0x8, 0xF],
    [0x6, 0x0, 0x2, 0x3],
    [0xC, 0x4, 0xD, 0xE]
]

# 轮常数（RCON）
RCON = [0x80, 0x30]  # RCON(1)=0x80, RCON(2)=0x30

# GF(2^4)乘法表（基于模x^4+x+1）
GF_MUL_TABLE = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    [0, 2, 4, 6, 8, 10, 12, 14, 3, 1, 7, 5, 11, 9, 15, 13],
    [0, 3, 6, 5, 12, 15, 10, 9, 11, 8, 13, 14, 7, 4, 1, 2],
    [0, 4, 8, 12, 3, 7, 11, 15, 6, 2, 14, 10, 5, 1, 13, 9],
    [0, 5, 10, 15, 7, 2, 13, 8, 14, 11, 4, 1, 9, 12, 3, 6],
    [0, 6, 12, 10, 11, 13, 7, 1, 5, 3, 9, 15, 14, 8, 2, 4],
    [0, 7, 14, 9, 15, 8, 1, 6, 13, 10, 3, 4, 2, 5, 12, 11],
    [0, 8, 3, 11, 6, 14, 5, 13, 12, 4, 15, 7, 10, 2, 9, 1],
    [0, 9, 1, 8, 2, 11, 3, 10, 4, 13, 5, 12, 6, 15, 7, 14],
    [0, 10, 7, 13, 14, 4, 9, 3, 15, 5, 8, 2, 1, 11, 6, 12],
    [0, 11, 5, 14, 10, 1, 15, 4, 7, 12, 2, 9, 13, 6, 8, 3],
    [0, 12, 11, 7, 5, 9, 14, 2, 10, 6, 1, 13, 15, 3, 4, 8],
    [0, 13, 9, 4, 1, 12, 8, 5, 2, 15, 11, 6, 3, 14, 10, 7],
    [0, 14, 15, 1, 13, 3, 2, 12, 9, 7, 6, 8, 4, 10, 11, 5],
    [0, 15, 13, 2, 9, 6, 4, 11, 1, 14, 12, 3, 8, 7, 5, 10]
]


# 核心算法函数
def sub_nibble(state):
    """半字节代替：对2x2状态矩阵的每个半字节执行S盒替换"""
    for i in range(2):
        for j in range(2):
            row = (state[i][j] >> 2) & 0x03
            col = state[i][j] & 0x03
            state[i][j] = S_BOX[row][col]
    return state


def inv_sub_nibble(state):
    """逆半字节代替：对2x2状态矩阵的每个半字节执行逆S盒替换"""
    for i in range(2):
        for j in range(2):
            row = (state[i][j] >> 2) & 0x03
            col = state[i][j] & 0x03
            state[i][j] = INV_S_BOX[row][col]
    return state


def shift_row(state):
    """行位移：第二行循环左移1个半字节"""
    state[1][0], state[1][1] = state[1][1], state[1][0]
    return state


def inv_shift_row(state):
    """逆行位移：与行位移操作相同"""
    return shift_row(state)


def mix_columns(state):
    """列混淆：基于GF(2^4)的矩阵乘法"""
    for j in range(2):
        col = [state[0][j], state[1][j]]
        state[0][j] = GF_MUL_TABLE[1][col[0]] ^ GF_MUL_TABLE[4][col[1]]
        state[1][j] = GF_MUL_TABLE[4][col[0]] ^ GF_MUL_TABLE[1][col[1]]
    return state


def inv_mix_columns(state):
    """逆列混淆：基于GF(2^4)的矩阵乘法"""
    for j in range(2):
        col = [state[0][j], state[1][j]]
        state[0][j] = GF_MUL_TABLE[9][col[0]] ^ GF_MUL_TABLE[2][col[1]]
        state[1][j] = GF_MUL_TABLE[2][col[0]] ^ GF_MUL_TABLE[9][col[1]]
    return state


def add_round_key(state, round_key):
    """轮密钥加：状态矩阵与轮密钥逐位异或"""
    key_matrix = [
        [round_key >> 12 & 0x0F, round_key >> 4 & 0x0F],
        [round_key >> 8 & 0x0F, round_key >> 0 & 0x0F]
    ]
    for i in range(2):
        for j in range(2):
            state[i][j] ^= key_matrix[i][j]
    return state


def key_expansion(key):
    """密钥扩展：16bit密钥扩展为3个16bit轮密钥"""
    w = [0] * 6
    w[0] = (key >> 8) & 0xFF
    w[1] = key & 0xFF

    for i in range(2, 6):
        if i % 2 == 0:
            rot_nib = ((w[i - 1] & 0x0F) << 4) | ((w[i - 1] >> 4) & 0x0F)
            sub_nib = (S_BOX[(rot_nib >> 4) & 0x03][rot_nib & 0x03] << 4) | \
                      S_BOX[(rot_nib >> 0) & 0x03][rot_nib & 0x0F & 0x03]
            w[i] = w[i - 2] ^ sub_nib ^ RCON[i // 2 - 1]
        else:
            w[i] = w[i - 2] ^ w[i - 1]

    return [(w[0] << 8) | w[1], (w[2] << 8) | w[3], (w[4] << 8) | w[5]]


def s_aes_encrypt(plaintext, key):
    """S-AES加密：16bit明文+16bit密钥→16bit密文"""
    state = [
        [(plaintext >> 12) & 0x0F, (plaintext >> 4) & 0x0F],
        [(plaintext >> 8) & 0x0F, (plaintext >> 0) & 0x0F]
    ]

    round_keys = key_expansion(key)
    state = add_round_key(state, round_keys[0])

    state = sub_nibble(state)
    state = shift_row(state)
    state = mix_columns(state)
    state = add_round_key(state, round_keys[1])

    state = sub_nibble(state)
    state = shift_row(state)
    state = add_round_key(state, round_keys[2])

    return (state[0][0] << 12) | (state[1][0] << 8) | (state[0][1] << 4) | state[1][1]


def s_aes_decrypt(ciphertext, key):
    """S-AES解密：16bit密文+16bit密钥→16bit明文"""
    state = [
        [(ciphertext >> 12) & 0x0F, (ciphertext >> 4) & 0x0F],
        [(ciphertext >> 8) & 0x0F, (ciphertext >> 0) & 0x0F]
    ]

    round_keys = key_expansion(key)
    state = add_round_key(state, round_keys[2])

    state = inv_shift_row(state)
    state = inv_sub_nibble(state)
    state = add_round_key(state, round_keys[1])
    state = inv_mix_columns(state)

    state = inv_shift_row(state)
    state = inv_sub_nibble(state)
    state = add_round_key(state, round_keys[0])

    return (state[0][0] << 12) | (state[1][0] << 8) | (state[0][1] << 4) | state[1][1]


# ASCII字符串加解密
def ascii_encrypt(text, key):
    """ASCII字符串加密：按2Bytes分组处理"""
    ciphertext = []
    for i in range(0, len(text), 2):
        group = text[i:i + 2]
        while len(group) < 2:
            group += chr(0x00)
        plaintext = (ord(group[0]) << 8) | ord(group[1])
        cipher = s_aes_encrypt(plaintext, key)
        ciphertext.append(chr((cipher >> 8) & 0xFF))
        ciphertext.append(chr(cipher & 0xFF))
    return ''.join(ciphertext)


def ascii_decrypt(ciphertext, key):
    """ASCII字符串解密：按2Bytes分组还原"""
    plaintext = []
    if len(ciphertext) % 2 != 0:
        raise ValueError("密文长度必须为偶数")
    for i in range(0, len(ciphertext), 2):
        group = ciphertext[i:i + 2]
        cipher = (ord(group[0]) << 8) | ord(group[1])
        plain = s_aes_decrypt(cipher, key)
        plain_chars = chr((plain >> 8) & 0xFF) + chr(plain & 0xFF)
        plaintext.append(plain_chars.rstrip(chr(0x00)))
    return ''.join(plaintext)


# 双重加密与中间相遇攻击
def double_encrypt(plaintext, key):
    """双重加密：32bit密钥（K1+K2）"""
    if key < 0 or key > 0xFFFFFFFF:
        raise ValueError("双重加密密钥必须为32bit")
    k1 = (key >> 16) & 0xFFFF
    k2 = key & 0xFFFF
    return s_aes_encrypt(s_aes_encrypt(plaintext, k1), k2)


def double_decrypt(ciphertext, key):
    """双重解密：32bit密钥（K1+K2）"""
    k1 = (key >> 16) & 0xFFFF
    k2 = key & 0xFFFF
    return s_aes_decrypt(s_aes_decrypt(ciphertext, k2), k1)


def meet_in_the_middle(plain_cipher_pairs):
    """中间相遇攻击：通过明密文对找到32bit双重加密密钥"""
    if not plain_cipher_pairs:
        raise ValueError("至少需要1对明密文对")

    p1, c1 = plain_cipher_pairs[0]
    forward_map = {}
    for k1 in range(0x10000):
        intermediate = s_aes_encrypt(p1, k1)
        forward_map[intermediate] = k1

    for k2 in range(0x10000):
        intermediate = s_aes_decrypt(c1, k2)
        if intermediate in forward_map:
            candidate_key = (forward_map[intermediate] << 16) | k2
            valid = True
            for p, c in plain_cipher_pairs[1:]:
                if double_encrypt(p, candidate_key) != c:
                    valid = False
                    break
            if valid:
                return candidate_key

    raise ValueError("未找到匹配的密钥，请提供更多明密文对")


# 三重加密
def triple_encrypt(plaintext, key, mode=1):
    """三重加密：支持两种模式"""
    if mode == 1:
        if key < 0 or key > 0xFFFFFFFF:
            raise ValueError("模式1密钥必须为32bit")
        k1 = (key >> 16) & 0xFFFF
        k2 = key & 0xFFFF
        step1 = s_aes_encrypt(plaintext, k2)
        step2 = s_aes_decrypt(step1, k1)
        return s_aes_encrypt(step2, k2)
    elif mode == 2:
        if key < 0 or key > 0xFFFFFFFFFF:
            raise ValueError("模式2密钥必须为48bit")
        k1 = (key >> 32) & 0xFFFF
        k2 = (key >> 16) & 0xFFFF
        k3 = key & 0xFFFF
        step1 = s_aes_encrypt(plaintext, k1)
        step2 = s_aes_decrypt(step1, k2)
        return s_aes_encrypt(step2, k3)
    else:
        raise ValueError("模式必须为1或2")


def triple_decrypt(ciphertext, key, mode=1):
    """三重解密：对应三重加密的逆过程"""
    if mode == 1:
        k1 = (key >> 16) & 0xFFFF
        k2 = key & 0xFFFF
        step1 = s_aes_decrypt(ciphertext, k2)
        step2 = s_aes_encrypt(step1, k1)
        return s_aes_decrypt(step2, k2)
    elif mode == 2:
        k1 = (key >> 32) & 0xFFFF
        k2 = (key >> 16) & 0xFFFF
        k3 = key & 0xFFFF
        step1 = s_aes_decrypt(ciphertext, k3)
        step2 = s_aes_encrypt(step1, k2)
        return s_aes_decrypt(step2, k1)
    else:
        raise ValueError("模式必须为1或2")


# CBC工作模式
def generate_iv():
    """生成16bit初始向量（IV）"""
    return random.randint(0, 0xFFFF)


def cbc_encrypt(plaintext_blocks, key, iv):
    """CBC模式加密：对多个16bit明文块加密"""
    cipher_blocks = []
    prev_block = iv
    for p_block in plaintext_blocks:
        xor_block = p_block ^ prev_block
        c_block = s_aes_encrypt(xor_block, key)
        cipher_blocks.append(c_block)
        prev_block = c_block
    return cipher_blocks


def cbc_decrypt(cipher_blocks, key, iv):
    """CBC模式解密：对多个16bit密文块解密"""
    plain_blocks = []
    prev_block = iv
    for c_block in cipher_blocks:
        decrypt_block = s_aes_decrypt(c_block, key)
        p_block = decrypt_block ^ prev_block
        plain_blocks.append(p_block)
        prev_block = c_block
    return plain_blocks


def cbc_encrypt_text(text, key, iv):
    """CBC模式文本加密：将ASCII文本转换为16bit块后加密"""
    plain_blocks = []
    for i in range(0, len(text), 2):
        b1 = ord(text[i]) if i < len(text) else 0
        b2 = ord(text[i + 1]) if (i + 1) < len(text) else 0
        plain_blocks.append((b1 << 8) | b2)

    cipher_blocks = cbc_encrypt(plain_blocks, key, iv)
    cipher_text = ''.join([chr((c >> 8) & 0xFF) + chr(c & 0xFF) for c in cipher_blocks])
    return cipher_text, plain_blocks, cipher_blocks


def cbc_decrypt_text(cipher_text, key, iv):
    """CBC模式文本解密：将密文字符串转换为16bit块后解密"""
    if len(cipher_text) % 2 != 0:
        raise ValueError("密文字符串长度必须为偶数")

    cipher_blocks = []
    for i in range(0, len(cipher_text), 2):
        b1 = ord(cipher_text[i])
        b2 = ord(cipher_text[i + 1])
        cipher_blocks.append((b1 << 8) | b2)

    plain_blocks = cbc_decrypt(cipher_blocks, key, iv)
    plain_text = ''
    for p_block in plain_blocks:
        b1 = (p_block >> 8) & 0xFF
        b2 = p_block & 0xFF
        if b1 != 0x00:
            plain_text += chr(b1)
        if b2 != 0x00:
            plain_text += chr(b2)
    return plain_text, plain_blocks, cipher_blocks


def cbc_tamper_cipher(cipher_blocks, tamper_index, tamper_value):
    """篡改CBC密文块：修改指定索引的密文块值"""
    if tamper_index < 0 or tamper_index >= len(cipher_blocks):
        raise ValueError("篡改索引超出密文块范围")
    tampered_blocks = cipher_blocks.copy()
    tampered_blocks[tamper_index] = tamper_value
    return tampered_blocks


# 图形化界面实现
class S_AES_GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("S-AES加密解密程序")
        self.setGeometry(100, 100, 800, 600)
        self.init_ui()

    def init_ui(self):
        """初始化UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # 第1关：基本测试
        self.basic_tab = QWidget()
        self.init_basic_tab()
        self.tabs.addTab(self.basic_tab, "第1关：基本测试（16bit）")

        # 第2关：交叉测试
        self.cross_tab = QWidget()
        self.init_cross_tab()
        self.tabs.addTab(self.cross_tab, "第2关：交叉测试")

        # 第3关：ASCII字符串
        self.ascii_tab = QWidget()
        self.init_ascii_tab()
        self.tabs.addTab(self.ascii_tab, "第3关：ASCII字符串")

        # 第4 关：多重加密
        self.multi_tab = QWidget()
        self.init_multi_tab()
        self.tabs.addTab(self.multi_tab, "第4关：多重加密")

        # 第5关：CBC工作模式
        self.cbc_tab = QWidget()
        self.init_cbc_tab()
        self.tabs.addTab(self.cbc_tab, "第5关：CBC工作模式")

    def init_basic_tab(self):
        """初始化基本测试标签页"""
        layout = QVBoxLayout(self.basic_tab)

        input_group = QGroupBox("输入（16bit，十六进制）")
        input_layout = QVBoxLayout(input_group)

        plain_layout = QHBoxLayout()
        plain_layout.addWidget(QLabel("明文："))
        self.basic_plain = QLineEdit()
        self.basic_plain.setPlaceholderText("例如：3243")
        plain_layout.addWidget(self.basic_plain)
        input_layout.addLayout(plain_layout)

        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("密钥："))
        self.basic_key = QLineEdit()
        self.basic_key.setPlaceholderText("例如：2D55")
        key_layout.addWidget(self.basic_key)
        input_layout.addLayout(key_layout)

        layout.addWidget(input_group)

        btn_layout = QHBoxLayout()
        self.basic_encrypt_btn = QPushButton("加密")
        self.basic_encrypt_btn.clicked.connect(self.basic_encrypt)
        self.basic_decrypt_btn = QPushButton("解密")
        self.basic_decrypt_btn.clicked.connect(self.basic_decrypt)
        btn_layout.addWidget(self.basic_encrypt_btn)
        btn_layout.addWidget(self.basic_decrypt_btn)
        layout.addLayout(btn_layout)

        output_group = QGroupBox("输出（16bit，十六进制）")
        output_layout = QVBoxLayout(output_group)
        self.basic_output = QTextEdit()
        self.basic_output.setReadOnly(True)
        output_layout.addWidget(self.basic_output)
        layout.addWidget(output_group)

    def basic_encrypt(self):
        """基本测试加密"""
        try:
            plain_hex = self.basic_plain.text().strip()
            key_hex = self.basic_key.text().strip()
            if not plain_hex or not key_hex:
                raise ValueError("明文和密钥不能为空")

            plaintext = int(plain_hex, 16)
            key = int(key_hex, 16)
            if plaintext < 0 or plaintext > 0xFFFF or key < 0 or key > 0xFFFF:
                raise ValueError("明文和密钥必须为16bit（0-FFFF）")

            ciphertext = s_aes_encrypt(plaintext, key)
            self.basic_output.setText(
                f"加密成功！\n"
                f"明文（十六进制）：{plain_hex.upper()}\n"
                f"密钥（十六进制）：{key_hex.upper()}\n"
                f"密文（十六进制）：{ciphertext:04X}"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加密失败：{str(e)}")

    def basic_decrypt(self):
        """基本测试解密"""
        try:
            cipher_hex = self.basic_plain.text().strip()
            key_hex = self.basic_key.text().strip()
            if not cipher_hex or not key_hex:
                raise ValueError("密文和密钥不能为空")

            ciphertext = int(cipher_hex, 16)
            key = int(key_hex, 16)
            if ciphertext < 0 or ciphertext > 0xFFFF or key < 0 or key > 0xFFFF:
                raise ValueError("密文和密钥必须为16bit（0-FFFF）")

            plaintext = s_aes_decrypt(ciphertext, key)
            self.basic_output.setText(
                f"解密成功！\n"
                f"密文（十六进制）：{cipher_hex.upper()}\n"
                f"密钥（十六进制）：{key_hex.upper()}\n"
                f"明文（十六进制）：{plaintext:04X}"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"解密失败：{str(e)}")

    def init_cross_tab(self):
        """初始化交叉测试标签页"""
        layout = QVBoxLayout(self.cross_tab)

        desc_label = QLabel("交叉测试：验证不同程序的加解密一致性")
        layout.addWidget(desc_label)

        input_group = QGroupBox("输入参数（十六进制）")
        input_layout = QVBoxLayout(input_group)

        p_layout = QHBoxLayout()
        p_layout.addWidget(QLabel("明文（16bit）："))
        self.cross_plain = QLineEdit()
        p_layout.addWidget(self.cross_plain)
        input_layout.addLayout(p_layout)

        k_layout = QHBoxLayout()
        k_layout.addWidget(QLabel("密钥（16bit）："))
        self.cross_key = QLineEdit()
        k_layout.addWidget(self.cross_key)
        input_layout.addLayout(k_layout)

        c_layout = QHBoxLayout()
        c_layout.addWidget(QLabel("其他组密文（16bit）："))
        self.cross_other_cipher = QLineEdit()
        c_layout.addWidget(self.cross_other_cipher)
        input_layout.addLayout(c_layout)

        layout.addWidget(input_group)

        self.cross_test_btn = QPushButton("开始交叉测试")
        self.cross_test_btn.clicked.connect(self.cross_test)
        layout.addWidget(self.cross_test_btn)

        self.cross_result = QTextEdit()
        self.cross_result.setReadOnly(True)
        layout.addWidget(self.cross_result)

    def cross_test(self):
        """交叉测试：比较本程序加密结果与其他组密文"""
        try:
            plain_hex = self.cross_plain.text().strip()
            key_hex = self.cross_key.text().strip()
            other_cipher_hex = self.cross_other_cipher.text().strip()
            if not plain_hex or not key_hex or not other_cipher_hex:
                raise ValueError("所有输入不能为空")

            plaintext = int(plain_hex, 16)
            key = int(key_hex, 16)
            other_cipher = int(other_cipher_hex, 16)

            for val, name in [(plaintext, "明文"), (key, "密钥"), (other_cipher, "其他组密文")]:
                if val < 0 or val > 0xFFFF:
                    raise ValueError(f"{name}必须为16bit（0-FFFF）")

            self_cipher = s_aes_encrypt(plaintext, key)
            self.cross_result.setText(
                f"交叉测试结果：\n"
                f"明文（十六进制）：{plain_hex.upper()}\n"
                f"密钥（十六进制）：{key_hex.upper()}\n"
                f"本程序加密密文：{self_cipher:04X}\n"
                f"其他组密文：{other_cipher_hex.upper()}\n\n"
                f"{'✅ 测试通过！两组程序加密结果一致' if self_cipher == other_cipher else '❌ 测试失败！两组程序加密结果不一致'}"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"测试失败：{str(e)}")

    def init_ascii_tab(self):
        """初始化ASCII字符串标签页"""
        layout = QVBoxLayout(self.ascii_tab)

        input_group = QGroupBox("输入")
        input_layout = QVBoxLayout(input_group)

        input_layout.addWidget(QLabel("ASCII文本（加密时输入明文，解密时输入密文）："))
        self.ascii_text = QTextEdit()
        input_layout.addWidget(self.ascii_text)

        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("密钥（16bit十六进制）："))
        self.ascii_key = QLineEdit()
        self.ascii_key.setPlaceholderText("例如：2D55")
        key_layout.addWidget(self.ascii_key)
        input_layout.addLayout(key_layout)

        layout.addWidget(input_group)

        btn_layout = QHBoxLayout()
        self.ascii_encrypt_btn = QPushButton("加密")
        self.ascii_encrypt_btn.clicked.connect(self.ascii_encrypt)
        self.ascii_decrypt_btn = QPushButton("解密")
        self.ascii_decrypt_btn.clicked.connect(self.ascii_decrypt)
        btn_layout.addWidget(self.ascii_encrypt_btn)
        btn_layout.addWidget(self.ascii_decrypt_btn)
        layout.addLayout(btn_layout)

        output_group = QGroupBox("输出")
        output_layout = QVBoxLayout(output_group)
        self.ascii_output = QTextEdit()
        self.ascii_output.setReadOnly(True)
        output_layout.addWidget(self.ascii_output)
        layout.addWidget(output_group)

    def ascii_encrypt(self):
        """ASCII字符串加密"""
        try:
            text = self.ascii_text.toPlainText().strip()
            key_hex = self.ascii_key.text().strip()
            if not text or not key_hex:
                raise ValueError("文本和密钥不能为空")

            key = int(key_hex, 16)
            if key < 0 or key > 0xFFFF:
                raise ValueError("密钥必须为16bit（0-FFFF）")

            ciphertext = ascii_encrypt(text, key)
            cipher_hex = ''.join([f"{ord(c):02X}" for c in ciphertext])
            self.ascii_output.setText(
                f"ASCII文本加密成功！\n"
                f"原始明文：{text}\n"
                f"密钥（十六进制）：{key_hex.upper()}\n"
                f"密文（原始）：{ciphertext}\n"
                f"密文（十六进制）：{cipher_hex.upper()}"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加密失败：{str(e)}")

    def ascii_decrypt(self):
        """ASCII字符串解密"""
        try:
            input_text = self.ascii_text.toPlainText().strip()
            key_hex = self.ascii_key.text().strip()
            if not input_text or not key_hex:
                raise ValueError("密文和密钥不能为空")

            key = int(key_hex, 16)
            if key < 0 or key > 0xFFFF:
                raise ValueError("密钥必须为16bit（0-FFFF）")

            is_hex = all(c in '0123456789ABCDEFabcdef' for c in input_text) and len(input_text) % 2 == 0
            if is_hex:
                ciphertext = ''.join([chr(int(input_text[i:i + 2], 16)) for i in range(0, len(input_text), 2)])
            else:
                ciphertext = input_text

            plaintext = ascii_decrypt(ciphertext, key)
            self.ascii_output.setText(
                f"ASCII文本解密成功！\n"
                f"输入密文类型：{'十六进制密文' if is_hex else '原始密文'}\n"
                f"密钥（十六进制）：{key_hex.upper()}\n"
                f"解密明文：{plaintext}"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"解密失败：{str(e)}")

    def init_multi_tab(self):
        """初始化多重加密标签页"""
        layout = QVBoxLayout(self.multi_tab)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("操作模式："))
        self.multi_mode = QComboBox()
        self.multi_mode.addItems([
            "双重加密", "双重解密",
            "三重加密（32bit密钥）", "三重加密（48bit密钥）",
            "三重解密（32bit密钥）", "三重解密（48bit密钥）",
            "中间相遇攻击"
        ])
        self.multi_mode.currentIndexChanged.connect(self.update_multi_inputs)
        mode_layout.addWidget(self.multi_mode)
        layout.addLayout(mode_layout)

        self.multi_input_group = QGroupBox("输入参数")
        self.multi_input_layout = QVBoxLayout(self.multi_input_group)
        layout.addWidget(self.multi_input_group)

        self.update_multi_inputs()

        self.multi_exec_btn = QPushButton("执行操作")
        self.multi_exec_btn.clicked.connect(self.multi_execute)
        layout.addWidget(self.multi_exec_btn)

        self.multi_output = QTextEdit()
        self.multi_output.setReadOnly(True)
        layout.addWidget(self.multi_output)

    def update_multi_inputs(self):
        """根据选择的模式更新输入区域"""
        for i in reversed(range(self.multi_input_layout.count())):
            widget = self.multi_input_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        mode = self.multi_mode.currentText()

        if "双重" in mode:
            pc_layout = QHBoxLayout()
            pc_label = QLabel("明文（十六进制）：" if "加密" in mode else "密文（十六进制）：")
            self.multi_pc = QLineEdit()
            self.multi_pc.setPlaceholderText("16bit，例如：3243")
            pc_layout.addWidget(pc_label)
            pc_layout.addWidget(self.multi_pc)
            self.multi_input_layout.addLayout(pc_layout)

            key_layout = QHBoxLayout()
            key_layout.addWidget(QLabel("32bit密钥（十六进制）："))
            self.multi_key = QLineEdit()
            self.multi_key.setPlaceholderText("32bit，例如：2D55A3F7")
            key_layout.addWidget(self.multi_key)
            self.multi_input_layout.addLayout(key_layout)

        elif "三重" in mode:
            pc_layout = QHBoxLayout()
            pc_label = QLabel("明文（十六进制）：" if "加密" in mode else "密文（十六进制）：")
            self.multi_pc = QLineEdit()
            self.multi_pc.setPlaceholderText("16bit，例如：3243")
            pc_layout.addWidget(pc_label)
            pc_layout.addWidget(self.multi_pc)
            self.multi_input_layout.addLayout(pc_layout)

            key_bits = 32 if "32bit" in mode else 48
            key_layout = QHBoxLayout()
            key_layout.addWidget(QLabel(f"{key_bits}bit密钥（十六进制）："))
            self.multi_key = QLineEdit()
            self.multi_key.setPlaceholderText(f"{key_bits}bit，例如：{'2D55A3F7' if key_bits == 32 else '2D55A3F71234'}")
            key_layout.addWidget(self.multi_key)
            self.multi_input_layout.addLayout(key_layout)

        elif mode == "中间相遇攻击":
            self.multi_input_layout.addWidget(QLabel("明密文对（每行一对，格式：明文(十六进制),密文(十六进制)）："))
            self.multi_pc_pairs = QTextEdit()
            self.multi_pc_pairs.setPlaceholderText("例如：\n3243,5A7B\n1234,8C9D")
            self.multi_input_layout.addWidget(self.multi_pc_pairs)

    def multi_execute(self):
        """执行多重加密/解密或中间相遇攻击"""
        try:
            mode = self.multi_mode.currentText()
            self.multi_output.clear()

            if mode == "双重加密":
                plain_hex = self.multi_pc.text().strip()
                key_hex = self.multi_key.text().strip()
                if not plain_hex or not key_hex:
                    raise ValueError("明文和密钥不能为空")

                plaintext = int(plain_hex, 16)
                key = int(key_hex, 16)
                if plaintext < 0 or plaintext > 0xFFFF or key < 0 or key > 0xFFFFFFFF:
                    raise ValueError("明文必须为16bit，密钥必须为32bit")

                ciphertext = double_encrypt(plaintext, key)
                self.multi_output.setText(
                    f"双重加密成功！\n"
                    f"明文（16bit十六进制）：{plain_hex.upper()}\n"
                    f"32bit密钥（十六进制）：{key_hex.upper()}\n"
                    f"密文（16bit十六进制）：{ciphertext:04X}"
                )

            elif mode == "双重解密":
                cipher_hex = self.multi_pc.text().strip()
                key_hex = self.multi_key.text().strip()
                if not cipher_hex or not key_hex:
                    raise ValueError("密文和密钥不能为空")

                ciphertext = int(cipher_hex, 16)
                key = int(key_hex, 16)
                if ciphertext < 0 or ciphertext > 0xFFFF or key < 0 or key > 0xFFFFFFFF:
                    raise ValueError("密文必须为16bit，密钥必须为32bit")

                plaintext = double_decrypt(ciphertext, key)
                self.multi_output.setText(
                    f"双重解密成功！\n"
                    f"密文（16bit十六进制）：{cipher_hex.upper()}\n"
                    f"32bit密钥（十六进制）：{key_hex.upper()}\n"
                    f"明文（16bit十六进制）：{plaintext:04X}"
                )

            elif mode == "三重加密（32bit密钥）":
                plain_hex = self.multi_pc.text().strip()
                key_hex = self.multi_key.text().strip()
                if not plain_hex or not key_hex:
                    raise ValueError("明文和密钥不能为空")

                plaintext = int(plain_hex, 16)
                key = int(key_hex, 16)
                if plaintext < 0 or plaintext > 0xFFFF or key < 0 or key > 0xFFFFFFFF:
                    raise ValueError("明文必须为16bit，密钥必须为32bit")

                ciphertext = triple_encrypt(plaintext, key, mode=1)
                self.multi_output.setText(
                    f"三重加密（32bit密钥）成功！\n"
                    f"加密模式：E(K2, D(K1, E(K2, P)))\n"
                    f"明文（16bit十六进制）：{plain_hex.upper()}\n"
                    f"32bit密钥（十六进制）：{key_hex.upper()}\n"
                    f"密文（16bit十六进制）：{ciphertext:04X}"
                )

            elif mode == "三重加密（48bit密钥）":
                plain_hex = self.multi_pc.text().strip()
                key_hex = self.multi_key.text().strip()
                if not plain_hex or not key_hex:
                    raise ValueError("明文和密钥不能为空")

                plaintext = int(plain_hex, 16)
                key = int(key_hex, 16)
                if plaintext < 0 or plaintext > 0xFFFF or key < 0 or key > 0xFFFFFFFFFF:
                    raise ValueError("明文必须为16bit，密钥必须为48bit")

                ciphertext = triple_encrypt(plaintext, key, mode=2)
                self.multi_output.setText(
                    f"三重加密（48bit密钥）成功！\n"
                    f"加密模式：E(K3, D(K2, E(K1, P)))\n"
                    f"明文（16bit十六进制）：{plain_hex.upper()}\n"
                    f"48bit密钥（十六进制）：{key_hex.upper()}\n"
                    f"密文（16bit十六进制）：{ciphertext:04X}"
                )

            elif mode == "三重解密（32bit密钥）":
                cipher_hex = self.multi_pc.text().strip()
                key_hex = self.multi_key.text().strip()
                if not cipher_hex or not key_hex:
                    raise ValueError("密文和密钥不能为空")

                ciphertext = int(cipher_hex, 16)
                key = int(key_hex, 16)
                if ciphertext < 0 or ciphertext > 0xFFFF or key < 0 or key > 0xFFFFFFFF:
                    raise ValueError("密文必须为16bit，密钥必须为32bit")

                plaintext = triple_decrypt(ciphertext, key, mode=1)
                self.multi_output.setText(
                    f"三重解密（32bit密钥）成功！\n"
                    f"解密模式：D(K2, E(K1, D(K2, C)))\n"
                    f"密文（16bit十六进制）：{cipher_hex.upper()}\n"
                    f"32bit密钥（十六进制）：{key_hex.upper()}\n"
                    f"明文（16bit十六进制）：{plaintext:04X}"
                )

            elif mode == "三重解密（48bit密钥）":
                cipher_hex = self.multi_pc.text().strip()
                key_hex = self.multi_key.text().strip()
                if not cipher_hex or not key_hex:
                    raise ValueError("密文和密钥不能为空")

                ciphertext = int(cipher_hex, 16)
                key = int(key_hex, 16)
                if ciphertext < 0 or ciphertext > 0xFFFF or key < 0 or key > 0xFFFFFFFFFF:
                    raise ValueError("密文必须为16bit，密钥必须为48bit")

                plaintext = triple_decrypt(ciphertext, key, mode=2)
                self.multi_output.setText(
                    f"三重解密（48bit密钥）成功！\n"
                    f"解密模式：D(K1, E(K2, D(K3, C)))\n"
                    f"密文（16bit十六进制）：{cipher_hex.upper()}\n"
                    f"48bit密钥（十六进制）：{key_hex.upper()}\n"
                    f"明文（16bit十六进制）：{plaintext:04X}"
                )

            elif mode == "中间相遇攻击":
                pairs_text = self.multi_pc_pairs.toPlainText().strip()
                if not pairs_text:
                    raise ValueError("明密文对不能为空")

                plain_cipher_pairs = []
                for line in pairs_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    if ',' not in line:
                        raise ValueError(f"无效格式：{line}（正确格式：明文,密文）")
                    p_hex, c_hex = line.split(',', 1)
                    p = int(p_hex.strip(), 16)
                    c = int(c_hex.strip(), 16)
                    if p < 0 or p > 0xFFFF or c < 0 or c > 0xFFFF:
                        raise ValueError("明密文必须为16bit")
                    plain_cipher_pairs.append((p, c))

                QMessageBox.information(self, "提示", "中间相遇攻击执行中（约需几秒）...")
                key = meet_in_the_middle(plain_cipher_pairs)

                self.multi_output.setText(f"中间相遇攻击成功！\n")
                self.multi_output.append(f"使用明密文对数量：{len(plain_cipher_pairs)}")
                for i, (p, c) in enumerate(plain_cipher_pairs, 1):
                    self.multi_output.append(f"第{i}对：明文=0x{p:04X}, 密文=0x{c:04X}")
                self.multi_output.append(f"\n找到的32bit密钥（十六进制）：{key:08X}")

                verify_ok = all(double_encrypt(p, key) == c for p, c in plain_cipher_pairs)
                self.multi_output.append(f"密钥验证：{'✅ 通过' if verify_ok else '❌ 失败'}")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"操作失败：{str(e)}")

    def init_cbc_tab(self):
        """初始化CBC工作模式标签页"""
        layout = QVBoxLayout(self.cbc_tab)

        input_group = QGroupBox("输入参数")
        input_layout = QVBoxLayout(input_group)

        input_layout.addWidget(QLabel("ASCII文本（加密时输入明文，解密时输入密文）："))
        self.cbc_text = QTextEdit()
        input_layout.addWidget(self.cbc_text)

        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("16bit密钥（十六进制）："))
        self.cbc_key = QLineEdit()
        self.cbc_key.setPlaceholderText("例如：2D55")
        key_layout.addWidget(self.cbc_key)
        input_layout.addLayout(key_layout)

        iv_layout = QHBoxLayout()
        iv_layout.addWidget(QLabel("16bit初始向量（IV，十六进制）："))
        self.cbc_iv = QLineEdit()
        self.cbc_iv.setPlaceholderText("加密时留空自动生成，解密时必须输入")
        iv_layout.addWidget(self.cbc_iv)

        self.generate_iv_btn = QPushButton("生成随机IV")
        self.generate_iv_btn.clicked.connect(self.generate_cbc_iv)
        iv_layout.addWidget(self.generate_iv_btn)
        input_layout.addLayout(iv_layout)

        layout.addWidget(input_group)

        btn_layout = QHBoxLayout()
        self.cbc_encrypt_btn = QPushButton("CBC加密")
        self.cbc_encrypt_btn.clicked.connect(self.cbc_encrypt)
        self.cbc_decrypt_btn = QPushButton("CBC解密")
        self.cbc_decrypt_btn.clicked.connect(self.cbc_decrypt)
        self.cbc_tamper_btn = QPushButton("密文篡改测试")
        self.cbc_tamper_btn.clicked.connect(self.cbc_tamper_test)
        btn_layout.addWidget(self.cbc_encrypt_btn)
        btn_layout.addWidget(self.cbc_decrypt_btn)
        btn_layout.addWidget(self.cbc_tamper_btn)
        layout.addLayout(btn_layout)

        output_group = QGroupBox("输出结果")
        output_layout = QVBoxLayout(output_group)
        self.cbc_output = QTextEdit()
        self.cbc_output.setReadOnly(True)
        output_layout.addWidget(self.cbc_output)
        layout.addWidget(output_group)

        self.cbc_encrypted_data = None  # 存储加密数据用于篡改测试

    def generate_cbc_iv(self):
        """生成随机IV"""
        iv = generate_iv()
        self.cbc_iv.setText(f"{iv:04X}")

    def cbc_encrypt(self):
        """CBC模式加密"""
        try:
            text = self.cbc_text.toPlainText().strip()
            key_hex = self.cbc_key.text().strip()
            iv_hex = self.cbc_iv.text().strip()

            if not text or not key_hex:
                raise ValueError("明文和密钥不能为空")

            key = int(key_hex, 16)
            if key < 0 or key > 0xFFFF:
                raise ValueError("密钥必须为16bit")

            if not iv_hex:
                iv = generate_iv()
                iv_hex = f"{iv:04X}"
                self.cbc_iv.setText(iv_hex)
            else:
                iv = int(iv_hex, 16)
                if iv < 0 or iv > 0xFFFF:
                    raise ValueError("IV必须为16bit")

            cipher_text, plain_blocks, cipher_blocks = cbc_encrypt_text(text, key, iv)
            self.cbc_encrypted_data = (cipher_text, plain_blocks, cipher_blocks, iv, key)

            cipher_hex = ''.join([f"{ord(c):02X}" for c in cipher_text])
            self.cbc_output.setText(
                f"CBC模式加密成功！\n"
                f"原始明文：{text}\n"
                f"16bit密钥：{key_hex.upper()}\n"
                f"16bit IV：{iv_hex.upper()}\n\n"
                f"明文块数量：{len(plain_blocks)}\n"
            )
            for i, (p, c) in enumerate(zip(plain_blocks, cipher_blocks), 1):
                self.cbc_output.append(f"第{i}块：明文=0x{p:04X}, 密文=0x{c:04X}")
            self.cbc_output.append(f"\n密文（十六进制）：{cipher_hex.upper()}")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"CBC加密失败：{str(e)}")

    def cbc_decrypt(self):
        """CBC模式解密"""
        try:
            input_text = self.cbc_text.toPlainText().strip()
            key_hex = self.cbc_key.text().strip()
            iv_hex = self.cbc_iv.text().strip()

            if not input_text or not key_hex or not iv_hex:
                raise ValueError("密文、密钥和IV不能为空")

            key = int(key_hex, 16)
            iv = int(iv_hex, 16)
            if key < 0 or key > 0xFFFF or iv < 0 or iv > 0xFFFF:
                raise ValueError("密钥和IV必须为16bit")

            is_hex = all(c in '0123456789ABCDEFabcdef' for c in input_text) and len(input_text) % 2 == 0
            cipher_text = ''.join(
                [chr(int(input_text[i:i + 2], 16)) for i in range(0, len(input_text), 2)]) if is_hex else input_text

            plain_text, plain_blocks, cipher_blocks = cbc_decrypt_text(cipher_text, key, iv)
            self.cbc_output.setText(
                f"CBC模式解密成功！\n"
                f"输入类型：{'十六进制密文' if is_hex else '原始密文'}\n"
                f"16bit密钥：{key_hex.upper()}\n"
                f"16bit IV：{iv_hex.upper()}\n\n"
                f"密文块数量：{len(cipher_blocks)}\n"
            )
            for i, (c, p) in enumerate(zip(cipher_blocks, plain_blocks), 1):
                self.cbc_output.append(f"第{i}块：密文=0x{c:04X}, 明文=0x{p:04X}")
            self.cbc_output.append(f"\n解密明文：{plain_text}")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"CBC解密失败：{str(e)}")

    def cbc_tamper_test(self):
        """CBC密文篡改测试"""
        try:
            if not self.cbc_encrypted_data:
                raise ValueError("请先执行CBC加密生成密文")

            cipher_text, plain_blocks, cipher_blocks, iv, key = self.cbc_encrypted_data
            if len(cipher_blocks) == 0:
                raise ValueError("无密文块可篡改")

            tamper_index = 0 if len(cipher_blocks) == 1 else 1
            original_cipher = cipher_blocks[tamper_index]
            tamper_value = original_cipher ^ 0x0001  # 篡改1位

            tampered_blocks = cbc_tamper_cipher(cipher_blocks, tamper_index, tamper_value)
            tampered_cipher_text = ''.join([chr((c >> 8) & 0xFF) + chr(c & 0xFF) for c in tampered_blocks])
            tampered_plain_text, _, _ = cbc_decrypt_text(tampered_cipher_text, key, iv)

            self.cbc_output.setText(
                f"CBC密文篡改测试结果：\n"
                f"篡改位置：第{tamper_index + 1}块密文\n"
                f"原始值：0x{original_cipher:04X}\n"
                f"篡改后值：0x{tamper_value:04X}\n\n"
                f"原始明文：{''.join([chr((p >> 8) & 0xFF) + chr(p & 0xFF) for p in plain_blocks]).rstrip(chr(0x00))}\n"
                f"篡改后解密明文：{tampered_plain_text}\n\n"
                f"结论：CBC模式中，单块密文篡改会影响当前块及后续块的解密结果"
            )

        except Exception as e:
            QMessageBox.warning(self, "错误", f"篡改测试失败：{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = S_AES_GUI()
    window.show()
    sys.exit(app.exec_())