#!/usr/bin/env bash
# Monitorar logs em tempo real enquanto testa o servidor

echo "🔍 Monitorando logs em tempo real..."
echo "📍 Abra http://localhost:5000 no navegador e teste as páginas"
echo "📋 Os logs aparecerão aqui ⬇️"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Garantir que o arquivo de log existe
mkdir -p logs
touch logs/app.log

# Monitorar em tempo real e colorizar
tail -f logs/app.log | sed '
  s/ERROR/\x1b[31mERROR\x1b[0m/g
  s/WARNING/\x1b[33mWARNING\x1b[0m/g
  s/INFO/\x1b[32mINFO\x1b[0m/g
  s/✓/\x1b[32m✓\x1b[0m/g
  s/✗/\x1b[31m✗\x1b[0m/g
  s/⚠/\x1b[33m⚠\x1b[0m/g
'
