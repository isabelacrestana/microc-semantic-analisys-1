from __future__ import annotations

from ast_nodes import (
    Assignment,
    BinaryExpr,
    Block,
    BoolLiteral,
    CallExpr,
    CallStmt,
    Expr,
    FunctionDecl,
    IdentifierExpr,
    IfStmt,
    IntLiteral,
    Parameter,
    PrintStmt,
    Program,
    ReturnStmt,
    Stmt,
    StringLiteral,
    TypeName,
    UnaryExpr,
    VarDecl,
    WhileStmt,
)
from semantic_errors import (
    SemanticDiagnostic,
    SemanticError,
    SemanticErrorKind,
)
from symbols import (
    FunctionSymbol,
    Scope,
    Symbol,
    SymbolKind,
)

class NameResolver:
    def __init__(self) -> None:
        # Tabela global de funções (espaço de nomes separado de variáveis)
        self.functions: dict[str, FunctionSymbol] = {}
        # Aponta para o escopo léxico ativo no momento
        self.current_scope: Scope | None = None
        # Acumula todos os diagnósticos da passagem
        self.diagnostics: list[SemanticDiagnostic] = []

    def collect_functions(self, program: Program) -> None:
        """Coleta assinaturas prévias para permitir chamadas antecipadas e recursão."""
        for func in program.functions:
            if func.name in self.functions:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.DUPLICATE_FUNCTION,
                        message=f"função '{func.name}' redeclarada",
                        span=func.span,
                    )
                )
            else:
                param_types = tuple(p.type for p in func.parameters)
                symbol = FunctionSymbol(
                    name=func.name,
                    kind=SymbolKind.FUNCTION,
                    type=func.return_type,
                    declaration=func,
                    parameter_types=param_types,
                )
                self.functions[func.name] = symbol
                func.metadata["symbol"] = symbol

    def check_main(self, program: Program) -> None:
        """Valida a existência e a assinatura exata de int main()."""
        if "main" not in self.functions:
            # Em caso de main ausente, o span utilizado é o do próprio Program
            self.diagnostics.append(
                SemanticDiagnostic(
                    kind=SemanticErrorKind.INVALID_MAIN,
                    message="função 'main' ausente",
                    span=program.span,
                )
            )
            return

        main = self.functions["main"]
        # main deve retornar int e não pode possuir parâmetros
        if main.parameter_types or main.type != TypeName.INT:
            self.diagnostics.append(
                SemanticDiagnostic(
                    kind=SemanticErrorKind.INVALID_MAIN,
                    message="função 'main' deve ter assinatura 'int main()'",
                    span=main.declaration.span,
                )
            )

    def resolve_function(self, func: FunctionDecl) -> None:
        """Inicializa o escopo raiz da função com seus parâmetros e visita o corpo."""
        body_scope = Scope(parent=None)
        func.body.metadata["scope"] = body_scope

        # Parâmetros compartilham o mesmo escopo do bloco externo da função
        for param in func.parameters:
            if param.name in body_scope.symbols:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                        message=f"parâmetro '{param.name}' duplicado",
                        span=param.span,
                    )
                )
            else:
                sym = Symbol(
                    name=param.name,
                    kind=SymbolKind.PARAMETER,
                    type=param.type,
                    declaration=param,
                )
                body_scope.symbols[param.name] = sym
                param.metadata["symbol"] = sym

        # Atualiza o escopo atual para o corpo da função e restaura na saída
        previous_scope = self.current_scope
        self.current_scope = body_scope

        for stmt in func.body.statements:
            self.resolve_stmt(stmt)

        self.current_scope = previous_scope

    def resolve_stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, VarDecl):
            # Não é permitido declarar variáveis com mesmo nome no mesmo escopo
            if stmt.name in self.current_scope.symbols:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                        message=f"variável '{stmt.name}' já declarada neste escopo",
                        span=stmt.span,
                    )
                )
            else:
                sym = Symbol(
                    name=stmt.name,
                    kind=SymbolKind.VARIABLE,
                    type=stmt.type,
                    declaration=stmt,
                )
                self.current_scope.symbols[stmt.name] = sym
                stmt.metadata["symbol"] = sym

            # A variável entra no escopo antes do inicializador (ex: int y = y)
            if stmt.initializer:
                self.resolve_expr(stmt.initializer)

        elif isinstance(stmt, Block):
            # Blocos aninhados criam um novo escopo filho (permite shadowing)
            child_scope = Scope(parent=self.current_scope)
            stmt.metadata["scope"] = child_scope

            previous_scope = self.current_scope
            self.current_scope = child_scope

            for s in stmt.statements:
                self.resolve_stmt(s)

            self.current_scope = previous_scope

        elif isinstance(stmt, Assignment):
            self.resolve_expr(stmt.target)
            self.resolve_expr(stmt.value)

        elif isinstance(stmt, IfStmt):
            self.resolve_expr(stmt.condition)
            self.resolve_stmt(stmt.then_block)
            if stmt.else_block:
                self.resolve_stmt(stmt.else_block)

        elif isinstance(stmt, WhileStmt):
            self.resolve_expr(stmt.condition)
            self.resolve_stmt(stmt.body)

        elif isinstance(stmt, ReturnStmt):
            if stmt.value:
                self.resolve_expr(stmt.value)

        elif isinstance(stmt, PrintStmt):
            # Apenas expressões precisam de resolução (strings puras são ignoradas aqui)
            for item in stmt.items:
                if isinstance(item, Expr):
                    self.resolve_expr(item)

        elif isinstance(stmt, CallStmt):
            self.resolve_expr(stmt.call)

    def resolve_expr(self, expr: Expr) -> None:
        if isinstance(expr, IdentifierExpr):
            # Busca a variável subindo pelos escopos pais
            curr = self.current_scope
            found = None
            while curr is not None:
                if expr.name in curr.symbols:
                    found = curr.symbols[expr.name]
                    break
                curr = curr.parent

            if found:
                expr.metadata["symbol"] = found
            else:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.UNDECLARED_VARIABLE,
                        message=f"variável '{expr.name}' não declarada",
                        span=expr.span,
                    )
                )

        elif isinstance(expr, CallExpr):
            # Funções são buscadas diretamente na tabela global
            if expr.name in self.functions:
                expr.metadata["symbol"] = self.functions[expr.name]
            else:
                self.diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.UNDECLARED_FUNCTION,
                        message=f"função '{expr.name}' não declarada",
                        span=expr.span,
                    )
                )

            # Visita todos os argumentos, mesmo se a função não existir
            for arg in expr.arguments:
                self.resolve_expr(arg)

        elif isinstance(expr, BinaryExpr):
            self.resolve_expr(expr.left)
            self.resolve_expr(expr.right)

        elif isinstance(expr, UnaryExpr):
            self.resolve_expr(expr.operand)


def resolve_names(program: Program) -> None:
    """Construa escopos, símbolos e vínculos entre usos e declarações."""
    resolver = NameResolver()
    resolver.collect_functions(program)
    resolver.check_main(program)

    for func in program.functions:
        resolver.resolve_function(func)

    if resolver.diagnostics:
        raise SemanticError(resolver.diagnostics)
