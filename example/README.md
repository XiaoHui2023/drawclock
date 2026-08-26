# 绘图示例

`draw.json` 各使用一种源、`from`、mux、PLL、分频器、DTO、反相器、cell、gate 和末端 clock。

```powershell
drawclock -i example/draw.json -l drawio-lib/drawclock -o example/generated/draw.svg
```

`auto-layout/` 包含线性、分支、复用、交叉和 512 至 4096 个末端时钟的压力配置。
