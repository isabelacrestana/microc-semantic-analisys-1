from __future__ import annotations

from ast_nodes import (
    Program, TypeName, FunctionDecl, Parameter, Block, Stmt, VarDecl,
    Assignment, CallStmt, IfStmt, WhileStmt, ReturnStmt, PrintStmt,
    Expr, BinaryExpr, UnaryExpr, CallExpr, IdentifierExpr, IntLiteral,
    BoolLiteral, StringLiteral, UnaryOperator, BinaryOperator
)
from ast_nodes import Program, TypeName
from semantic_errors import SemanticDiagnostic, SemanticError, SemanticErrorKind
from symbols import FunctionSymbol

    # 1. Use os símbolos anexados pela resolução de nomes.
    # 2. Determine cada expressão de baixo para cima.
    # 3. Valide operadores, chamadas, comandos e declarações.
    # 4. Anote expressões válidas e acumule os diagnósticos da passagem.


def check_types(program: Program) -> None:
    """Determine tipos de expressões e valide seus contextos."""

    class _UnknowType:
        pass


    UNKNOWN = _UnknowType

    class TypeChecker:
        def __init__(self, program: Program):
            self.program = program
            self.diagnostics: list[SemanticDiagnostic] = []
            

        def check_functions(self):

            for function in self.program.functions:
                for parameter in function.parameters:

                    if parameter == TypeName.VOID:
                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.VOID_PARAMETER,
                            f"Parametro '{parameter.name} não pode ser do tipo void",
                            parameter.span
                        ))

                self.check_block(function.body)
 


        def check_block(self, block: Block):
            for statement in block.statements:
                self.check_statements(statement)

        def check_statement(self, statement: Stmt):
            if isinstance(statement, VarDecl):
                if statement.type == TypeName.VOID:

                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.VOID_VARIABLE,
                        f"Variável '{statement.name} não pode ser do tipo void",
                        statement.span
                    ))

                if statement.initializer:

                    init_type = self.check_expression(statement.initializer)

                    if init_type is not UNKNOWN:

                        if init_type == TypeName.VOID:

                            self.diagnostics.append(SemanticDiagnostic(
                                SemanticErrorKind.VOID_VALUE_USED,
                                "Valor void não pode ser usado na inicialização.",
                                statement.initializer.span
                            ))
                        elif init_type != statement.type:

                            self.diagnostics.append(SemanticDiagnostic(
                                SemanticErrorKind.INITIALIZER_TYPE_MISMATCH,
                                "Tipo incompatível na inicialização da variável.",
                                statement.span
                            ))

            elif isinstance(statement, Assignment):
                variable_type = statement.target.metadata["symbol"].type
                value_type = self.check_expression(statement.value)

                self.check_expressions(statement.target)

                value_type = self.check_expression(statement.value)

                if value_type is not UNKNOWN and variable_type is not UNKNOWN:
                    if value_type == TypeName.VOID:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.VOID_VALUE_USED,
                            "Valor void não pode ser atribuído.",
                            statement.value.span
                        ))

                    elif value_type != variable_type:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.ASSIGNMENT_TYPE_MISMATCH,
                            "O tipo da expressão não corresponde ao da variável.",
                            statement.span
                        ))

            elif isinstance(statement, CallStmt):
                self.check_expression(statement.call)

            elif isinstance(statement, IfStmt):

                cond_type = self.check_expression(statement.condition)

                if cond_type is not UNKNOWN:
                    if cond_type == TypeName.VOID:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.VOID_VALUE_USED,
                            "Valor void usado na condição do if.",
                            statement.condition.span
                        ))

                    elif cond_type != TypeName.BOOL:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.CONDITION_TYPE_MISMATCH,
                            "Condição do if deve ser do tipo bool.",
                            statement.condition.span
                        ))

                self.check_block(statement.then_block)

                if statement.else_block:
                    self.check_block(statement.else_block)

            elif isinstance(statement, WhileStmt):

                cond_type = self.check_expression(statement.condition)

                if cond_type is not UNKNOWN:
                    if cond_type == TypeName.VOID:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.VOID_VALUE_USED,
                            "Valor void usado na condição do while.",
                            statement.condition.span
                        ))

                    elif cond_type != TypeName.BOOL:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.CONDITION_TYPE_MISMATCH,
                            "Condição do while deve ser do tipo bool.",
                            statement.condition.span
                        ))

                    self.check_block(statement.body)

            elif isinstance(statement, ReturnStmt):

                ret_expected = self.current_function.return_type

                if statement.value:

                    val_type = self.check_expression(statement.value)

                    if ret_expected == TypeName.VOID:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.RETURN_MISMATCH,
                            "Função com retorno void não pode retornar um valor.",
                            statement.span
                        ))

                    elif val_type is not UNKNOWN:
                        if val_type == TypeName.VOID:

                            self.diagnostics.append(SemanticDiagnostic(
                                SemanticErrorKind.VOID_VALUE_USED,
                                "Expressão void não pode ser retornada.",
                                statement.value.span
                            ))

                        elif val_type != ret_expected:

                            self.diagnostics.append(SemanticDiagnostic(
                                SemanticErrorKind.RETURN_MISMATCH,
                                "Tipo de retorno incompatível com a assinatura da função.",
                                statement.span
                            ))
                else:
                    if ret_expected != TypeName.VOID:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.RETURN_MISMATCH,
                            "A função não-void exige um valor de retorno.",
                            statement.span
                        ))

            elif isinstance(statement, PrintStmt):
                for item in statement.items:

                    if isinstance(item, Expr):

                        val_type = self.check_expression(item)

                        if val_type is not UNKNOWN and val_type == TypeName.VOID:

                            self.diagnostics.append(SemanticDiagnostic(
                                SemanticErrorKind.VOID_VALUE_USED,
                                "Valor void usado no comando print.",
                                item.span
                            ))

            elif isinstance(statement, Block):
                self.check_block(statement)

        def _check_expr_internal(self, expr: Expr) -> TypeName:
            if isinstance(expr, IntLiteral):
                
                if not (0 <= expr.value <= 9223372036854775807):

                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.INTEGER_LITERAL_OUT_OF_RANGE,
                        "Literal inteiro fora dos limites permitidos.",
                        expr.span
                    ))

                return TypeName.INT

            elif isinstance(expr, BoolLiteral):
                return TypeName.BOOL

            elif isinstance(expr, IdentifierExpr):
                symbol = expr.metadata.get("symbol")
                if symbol:
                    return symbol.type
                return UNKNOWN  # Capturado por erros não resolvidos da Passagem 1

            elif isinstance(expr, UnaryExpr):

                op_type = self.check_expression(expr.operand)

                if op_type is UNKNOWN:
                    return UNKNOWN
                
                if op_type == TypeName.VOID:

                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.VOID_VALUE_USED,
                        "Valor void usado em operação unária.",
                        expr.operand.span
                    ))

                    return UNKNOWN

                if expr.operator == UnaryOperator.NEGATE:
                    if op_type != TypeName.INT:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.INVALID_UNARY_OPERAND,
                            "O operador unário '-' exige int.",
                            expr.span
                        ))

                        return UNKNOWN
                    
                    return TypeName.INT
                
                elif expr.operator == UnaryOperator.NOT:
                    if op_type != TypeName.BOOL:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.INVALID_UNARY_OPERAND,
                            "O operador unário '!' exige bool.",
                            expr.span
                        ))

                        return UNKNOWN
                    
                    return TypeName.BOOL

            elif isinstance(expr, BinaryExpr):

                left_type = self.check_expression(expr.left)
                right_type = self.check_expression(expr.right)
                
                if left_type == TypeName.VOID:

                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.VOID_VALUE_USED,
                        "Valor void usado em operação binária.",
                        expr.left.span
                    ))

                if right_type == TypeName.VOID:

                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.VOID_VALUE_USED,
                        "Valor void usado em operação binária.",
                        expr.right.span
                    ))
                    
                if (left_type is UNKNOWN or right_type is UNKNOWN or 
                    left_type == TypeName.VOID or right_type == TypeName.VOID):

                    return UNKNOWN

                if expr.operator in (BinaryOperator.ADD, BinaryOperator.SUBTRACT, BinaryOperator.MULTIPLY, BinaryOperator.DIVIDE, BinaryOperator.REMAINDER):
                    
                    if left_type != TypeName.INT or right_type != TypeName.INT:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.INVALID_BINARY_OPERANDS,
                            "Operadores aritméticos exigem operandos do tipo int.",
                            expr.span
                        ))

                        return UNKNOWN
                    
                    return TypeName.INT

                elif expr.operator in (BinaryOperator.LESS, BinaryOperator.LESS_EQUAL, BinaryOperator.GREATER, BinaryOperator.GREATER_EQUAL):
                    if left_type != TypeName.INT or right_type != TypeName.INT:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.INVALID_BINARY_OPERANDS,
                            "Operadores relacionais exigem operandos do tipo int.",
                            expr.span
                        ))

                        return UNKNOWN
                    
                    return TypeName.BOOL

                elif expr.operator in (BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL):
                    if left_type != right_type:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.INVALID_BINARY_OPERANDS,
                            "Operadores de igualdade exigem operandos do mesmo tipo.",
                            expr.span
                        ))

                        return UNKNOWN
                    
                    return TypeName.BOOL

                elif expr.operator in (BinaryOperator.LOGICAL_AND, BinaryOperator.LOGICAL_OR):
                    if left_type != TypeName.BOOL or right_type != TypeName.BOOL:

                        self.diagnostics.append(SemanticDiagnostic(
                            SemanticErrorKind.INVALID_BINARY_OPERANDS,
                            "Operadores lógicos exigem operandos do tipo bool.",
                            expr.span
                        ))

                        return UNKNOWN
                    
                    return TypeName.BOOL

            elif isinstance(expr, CallExpr):
                symbol = expr.metadata.get("symbol")
                
                # Valida todos os argumentos de baixo para cima
                arg_types = []
                for arg in expr.arguments:
                    arg_types.append(self.check_expression(arg))

                if not symbol or not isinstance(symbol, FunctionSymbol):
                    return UNKNOWN
                
                # Aridade
                if len(expr.arguments) != len(symbol.parameter_types):
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.ARITY_MISMATCH,
                        "Número de argumentos incompatível com a assinatura da função.",
                        expr.span
                    ))
                
                # Tipagem de argumentos
                for i, (arg_type, expected) in enumerate(zip(arg_types, symbol.parameter_types)):
                    if arg_type is not UNKNOWN:

                        if arg_type == TypeName.VOID:

                            self.diagnostics.append(SemanticDiagnostic(
                                SemanticErrorKind.VOID_VALUE_USED,
                                f"Valor void não pode ser passado como argumento.",
                                expr.arguments[i].span
                            ))

                        elif arg_type != expected:

                            self.diagnostics.append(SemanticDiagnostic(
                                SemanticErrorKind.ARGUMENT_TYPE_MISMATCH,
                                f"Argumento na posição {i+1} incompatível.",
                                expr.arguments[i].span
                            ))

                return symbol.type
            
            return UNKNOWN


    program_checked = TypeChecker(program)
    program_checked.check_functions()


    if program_checked.diagnostics:
        raise SemanticError(diagnostics=program_checked.diagnostics)











