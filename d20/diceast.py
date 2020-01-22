import abc
import os

from lark import Lark, Transformer


# noinspection PyMethodMayBeStatic
# shush, you
class RollTransformer(Transformer):
    _comma = object()

    def expr(self, num_comment):
        return Expression(*num_comment)

    def comparison(self, binop):
        return BinOp(*binop)

    def a_num(self, binop):
        return BinOp(*binop)

    def m_num(self, binop):
        return BinOp(*binop)

    def u_num(self, unop):
        return UnOp(*unop)

    def numexpr(self, num_anno):
        return AnnotatedNumber(*num_anno)

    def literal(self, num):
        return Literal(*num)

    def set(self, opset):
        return OperatedSet(*opset)

    def set_op(self, opsel):
        return SetOperator.new(*opsel)

    def setexpr(self, the_set):
        if len(the_set) == 1 and the_set[-1] is not self._comma:
            return Parenthetical(the_set[0])
        elif len(the_set) and the_set[-1] is self._comma:
            the_set = the_set[:-1]
        return NumberSet(the_set)

    def dice(self, opdice):
        return OperatedDice(*opdice)

    def dice_op(self, opsel):
        return SetOperator.new(*opsel)

    def diceexpr(self, dice):
        if len(dice) == 1:
            return Dice(1, *dice)
        return Dice(*dice)

    def selector(self, sel):
        return SetSelector(*sel)

    def comma(self, _):
        return self._comma


class Node(abc.ABC):
    @property
    def children(self):
        """
        Returns a list of this node's roll children.

        :rtype: list of Node
        """
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError


class Expression(Node):  # expr
    __slots__ = ("roll", "comment")

    def __init__(self, roll, comment=None):
        self.roll = roll
        self.comment = str(comment) if comment is not None else None

    @property
    def children(self):
        return [self.roll]

    def __str__(self):
        if self.comment:
            return f"{str(self.roll)} {self.comment}"
        return str(self.roll)


class AnnotatedNumber(Node):  # numexpr
    __slots__ = ("value", "annotations")

    def __init__(self, value, *annotations):
        """
        :type value: Node
        :type annotations: lark.Token or str
        """
        super().__init__()
        self.value = value
        self.annotations = [str(a) for a in annotations]

    @property
    def children(self):
        return [self.value]

    def __str__(self):
        return f"{str(self.value)} {''.join(self.annotations)}"


class Literal(Node):  # literal
    __slots__ = ("value",)

    def __init__(self, value):
        """
        :type value: lark.Token or str
        """
        super().__init__()
        self.value = int(value) if value.type == 'INTEGER' else float(value)

    @property
    def children(self):
        return []

    def __str__(self):
        return str(self.value)


class Parenthetical(Node):
    __slots__ = ("value",)

    def __init__(self, value):
        """
        :type value: Node
        """
        super().__init__()
        self.value = value

    @property
    def children(self):
        return [self.value]

    def __str__(self):
        return f"({str(self.value)})"


class UnOp(Node):  # u_num
    __slots__ = ("op", "value")

    def __init__(self, op, value):
        """
        :type op: lark.Token or str
        :type value: Node
        """
        super().__init__()
        self.op = str(op)
        self.value = value

    @property
    def children(self):
        return [self.value]

    def __str__(self):
        return f"{self.op}{str(self.value)}"


class BinOp(Node):  # a_num, m_num
    __slots__ = ("op", "left", "right")

    def __init__(self, left, op, right):
        """
        :type op: lark.Token or str
        :type left: Node
        :type right: Node
        """
        super().__init__()
        self.op = str(op)
        self.left = left
        self.right = right

    @property
    def children(self):
        return [self.left, self.right]

    def __str__(self):
        return f"{str(self.left)} {self.op} {str(self.right)}"


class SetOperator:  # set_op, dice_op
    __slots__ = ("op", "sels")

    IMMEDIATE = {"mi", "ma"}

    def __init__(self, op, sels):
        """
        :type op: lark.Token or str
        :type sels: list of SetSelector
        """
        self.op = str(op)
        self.sels = sels

    @classmethod
    def new(cls, op, sel):
        return cls(op, [sel])

    def add_sels(self, sels):
        self.sels.extend(sels)

    def __str__(self):
        return "".join([f"{self.op}{str(sel)}" for sel in self.sels])


class SetSelector:  # selector
    __slots__ = ("cat", "num")

    def __init__(self, cat, num):
        """
        :type cat: lark.Token or None
        :type num: int
        """
        self.cat = str(cat) if cat is not None else None
        self.num = int(num)

    def __str__(self):
        if self.cat:
            return f"{self.cat}{self.num}"
        return str(self.num)


class OperatedSet(Node):  # set
    __slots__ = ("value", "operations")

    def __init__(self, the_set, *operations):
        """
        :type the_set: NumberSet or Dice
        :type operations: SetOperator
        """
        super().__init__()
        self.value = the_set
        self.operations = operations
        self._simplify_operations()

    @property
    def children(self):
        return [self.value]

    def _simplify_operations(self):
        """Simplifies expressions like k1k2k3 into k(1,2,3)."""
        new_operations = []

        for operation in self.operations:
            if operation.op in SetOperator.IMMEDIATE or not new_operations:
                new_operations.append(operation)
            else:
                last_op = new_operations[-1]
                if operation.op == last_op.op:
                    last_op.add_sels(operation.sels)
                else:
                    new_operations.append(operation)

        self.operations = new_operations

    def __str__(self):
        return f"{str(self.value)}{''.join([str(op) for op in self.operations])}"


class NumberSet(Node):  # setexpr
    __slots__ = ("values",)

    def __init__(self, values):
        """
        :type values: list of Node
        """
        super().__init__()
        self.values = list(values)

    @property
    def children(self):
        return self.values

    def __str__(self):
        out = f"{', '.join([str(v) for v in self.values])}"
        if len(self.values) == 1:
            return f"({out},)"
        return f"({out})"


class OperatedDice(OperatedSet):  # dice
    __slots__ = ()

    def __init__(self, the_dice, *operations):
        """
        :type the_dice: Dice
        :type operations: SetOperator
        """
        super().__init__(the_dice, *operations)


class Dice(Node):  # diceexpr
    __slots__ = ("num", "size")

    def __init__(self, num, size):
        """
        :type num: lark.Token or int
        :type size: lark.Token or int
        """
        super().__init__()
        self.num = int(num)
        self.size = int(size)

    @property
    def children(self):
        return []

    def __str__(self):
        return f"{self.num}d{self.size}"


with open(os.path.join(os.path.dirname(__file__), 'grammar.lark')) as f:
    grammar = f.read()
parser = Lark(grammar, start='expr', parser='lalr', transformer=RollTransformer())

if __name__ == '__main__':
    while True:
        parser = Lark(grammar, start='expr', parser='lalr')
        result = parser.parse(input())
        print(result.pretty())
        print(result)
        expr = RollTransformer().transform(result)
        print(str(expr))