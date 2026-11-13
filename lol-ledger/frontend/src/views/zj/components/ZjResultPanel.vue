<template>
  <section class="result">
    <div class="result-head">
      <span class="result-title">统计结果</span>
      <span class="legend">
        <i class="dot win"></i>五子登科=胜
        <i class="dot lose"></i>满载SUV=负
      </span>
      <span class="spacer"></span>
      <span v-if="rows.length" class="result-count">{{ rows.length }} 人</span>
    </div>

    <div v-if="!rows.length && !failed.length" class="empty">
      还没有数据。粘贴玩家列表，点「开始查询」后结果会出现在这里。
    </div>

    <template v-else>
      <el-table
        v-if="rows.length"
        class="desktop-only result-table"
        :data="rows"
        :row-key="(row: ZjResultRow) => row.player.full"
        size="small"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="matches">
              <div
                v-for="(match, index) in row.stat.list"
                :key="`${row.player.full}-${index}`"
                class="match"
                :class="match.win ? 'win' : 'lose'"
              >
                <img
                  v-if="match.championId"
                  class="match-icon"
                  :src="champIcon(match.championId)"
                  alt=""
                  @error="hideImage"
                />
                <span class="match-res" :class="match.win ? 'win' : 'lose'">
                  {{ match.win ? '五子登科' : '满载SUV' }}
                </span>
                <span class="match-mode">
                  {{ match.mode }}<template v-if="match.pos"> · {{ match.pos }}</template>
                </span>
                <span class="match-kda">
                  <template v-if="match.kda">
                    {{ match.kda.rating != null ? match.kda.rating : '' }}({{ match.kda.k }}-{{
                      match.kda.d
                    }}-{{ match.kda.a }})
                  </template>
                  <template v-else>-</template>
                </span>
                <span class="match-time">{{ match.time }}</span>
              </div>
              <div v-if="!row.stat.list.length" class="matches-empty">这名玩家没有「新模式」对局</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="玩家" min-width="130">
          <template #default="{ row }">
            <div class="pname">{{ row.player.name }}</div>
            <div class="pid">#{{ row.player.id }}</div>
          </template>
        </el-table-column>

        <el-table-column label="场次" width="70" align="right">
          <template #default="{ row }">
            <b class="mono">{{ row.stat.games }}</b>
          </template>
        </el-table-column>

        <el-table-column label="胜负" width="86" align="center">
          <template #default="{ row }">
            <span class="win-num">{{ row.stat.wins }}</span>
            <span class="slash">/</span>
            <span class="lose-num">{{ row.stat.losses }}</span>
          </template>
        </el-table-column>

        <el-table-column label="胜率" width="170">
          <template #default="{ row }">
            <div class="rate">
              <div class="rate-bar">
                <i
                  :style="{
                    width: `${(row.stat.winRate * 100).toFixed(1)}%`,
                    background: rateColor(row.stat.winRate),
                  }"
                ></i>
              </div>
              <b class="mono" :style="{ color: rateColor(row.stat.winRate) }">
                {{ (row.stat.winRate * 100).toFixed(1) }}%
              </b>
              <span v-if="row.stat.winRate >= 0.8" class="tag win">五子</span>
              <span v-else-if="row.stat.winRate < 0.4" class="tag lose">SUV</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="平均 KDA" width="130" align="right">
          <template #default="{ row }">
            <template v-if="row.stat.avgKDA">
              <b class="mono">{{ row.stat.avgKDA.rating.toFixed(2) }}</b>
              <span class="kda-sub">
                ({{ row.stat.avgKDA.k }}-{{ row.stat.avgKDA.d }}-{{ row.stat.avgKDA.a }})
              </span>
            </template>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="胜场最多英雄" min-width="150">
          <template #default="{ row }">
            <div v-if="row.stat.champWinRank.length" class="champs">
              <div v-for="champ in row.stat.champWinRank" :key="`w-${champ.id}`" class="champ">
                <img :src="champIcon(champ.id)" alt="" @error="hideImage" />
                <span>
                  {{ champ.name }}
                  <small>{{ champ.win }}胜/{{ champ.play }}场</small>
                </span>
              </div>
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="玩得最多英雄" min-width="150">
          <template #default="{ row }">
            <div v-if="row.stat.champPlayRank.length" class="champs">
              <div v-for="champ in row.stat.champPlayRank" :key="`p-${champ.id}`" class="champ">
                <img :src="champIcon(champ.id)" alt="" @error="hideImage" />
                <span>
                  {{ champ.name }}
                  <small>{{ champ.play }}场</small>
                </span>
              </div>
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="最常位置" width="110">
          <template #default="{ row }">
            <div v-if="row.stat.posRank.length">
              <div v-for="(pos, index) in row.stat.posRank" :key="pos.key" :class="{ sub: index > 0 }">
                <b>{{ pos.name }}</b>
                <span class="muted"> {{ pos.count }}场</span>
              </div>
            </div>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="mobile-only cards">
        <div v-for="row in rows" :key="row.player.full" class="card">
          <div class="card-head">
            <div>
              <div class="pname">{{ row.player.name }}</div>
              <div class="pid">#{{ row.player.id }}</div>
            </div>
            <div class="card-rate" :style="{ color: rateColor(row.stat.winRate) }">
              {{ (row.stat.winRate * 100).toFixed(1) }}%
            </div>
          </div>

          <div class="rate">
            <div class="rate-bar">
              <i
                :style="{
                  width: `${(row.stat.winRate * 100).toFixed(1)}%`,
                  background: rateColor(row.stat.winRate),
                }"
              ></i>
            </div>
          </div>

          <div class="card-meta">
            <span>新模式 <b>{{ row.stat.games }}</b> 场</span>
            <span><b class="win-num">{{ row.stat.wins }}</b>胜 / <b class="lose-num">{{ row.stat.losses }}</b>负</span>
            <span v-if="row.stat.avgKDA">KDA <b>{{ row.stat.avgKDA.rating.toFixed(2) }}</b></span>
            <span v-if="row.stat.posRank.length">主玩 {{ row.stat.posRank[0].name }}</span>
          </div>

          <details v-if="row.stat.list.length">
            <summary>对局明细（{{ row.stat.list.length }}）</summary>
            <div class="matches">
              <div
                v-for="(match, index) in row.stat.list"
                :key="`m-${row.player.full}-${index}`"
                class="match"
                :class="match.win ? 'win' : 'lose'"
              >
                <span class="match-res" :class="match.win ? 'win' : 'lose'">
                  {{ match.win ? '胜' : '负' }}
                </span>
                <span class="match-mode">{{ match.mode }} · {{ match.pos || '-' }}</span>
                <span class="match-kda" v-if="match.kda">
                  {{ match.kda.k }}-{{ match.kda.d }}-{{ match.kda.a }}
                </span>
                <span class="match-time">{{ match.time }}</span>
              </div>
            </div>
          </details>
        </div>
      </div>

      <div v-if="failed.length" class="failed">
        失败/无数据：
        <span v-for="item in failed" :key="item.player.full" class="failed-item">
          {{ item.player.full }}（{{ item.error || '无新模式数据' }}）
        </span>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { champIcon } from '@/utils/zjStats'

import type { ZjResultRow } from '../types'

withDefaults(
  defineProps<{
    rows: ZjResultRow[]
    failed?: ZjResultRow[]
  }>(),
  { failed: () => [] },
)

function rateColor(winRate: number): string {
  return winRate >= 0.5 ? '#3ecf8e' : '#ff6b6b'
}

function hideImage(event: Event) {
  ;(event.target as HTMLImageElement).style.visibility = 'hidden'
}
</script>

<style scoped>
.result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.result-title {
  font-size: 14px;
  font-weight: 600;
}

.result-count {
  font-size: 12px;
  color: var(--app-text-muted);
}

.legend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.dot.win {
  background: #3ecf8e;
}

.dot.lose {
  background: #ff6b6b;
}

.empty {
  padding: 34px 0;
  text-align: center;
  font-size: 13px;
  color: var(--app-text-muted);
}

.pname {
  font-weight: 600;
  font-size: 13px;
  line-height: 1.4;
}

.pid {
  font-size: 11.5px;
  color: var(--app-text-muted);
  font-variant-numeric: tabular-nums;
}

.win-num {
  color: #3ecf8e;
  font-weight: 600;
}

.lose-num {
  color: #ff6b6b;
  font-weight: 600;
}

.slash {
  color: var(--app-text-faint);
  margin: 0 3px;
}

.rate {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rate-bar {
  flex: 1;
  min-width: 46px;
  height: 7px;
  border-radius: 999px;
  background: var(--app-bg-subtle);
  overflow: hidden;
}

.rate-bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  transition: width 0.4s ease;
}

.tag {
  padding: 0 5px;
  border-radius: 4px;
  font-size: 10.5px;
  font-weight: 700;
}

.tag.win {
  background: rgba(62, 207, 142, 0.14);
  color: #3ecf8e;
}

.tag.lose {
  background: rgba(255, 92, 92, 0.14);
  color: #ff8080;
}

.kda-sub {
  font-size: 11px;
  color: var(--app-text-muted);
}

.champs {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.champ {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 1.3;
}

.champ img {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid var(--app-border);
  object-fit: cover;
}

.champ small {
  display: block;
  color: var(--app-text-muted);
  font-size: 11px;
}

.sub {
  font-size: 11.5px;
  color: var(--app-text-muted);
}

.matches {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 10px 10px;
}

.match {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
}

.match.win {
  background: rgba(62, 207, 142, 0.08);
}

.match.lose {
  background: rgba(255, 92, 92, 0.07);
}

.match-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid var(--app-border);
}

.match-res {
  flex: 0 0 58px;
  font-weight: 700;
}

.match-res.win {
  color: #3ecf8e;
}

.match-res.lose {
  color: #ff6b6b;
}

.match-mode {
  flex: 1;
  color: var(--el-text-color-regular);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.match-kda {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.match-time {
  width: 100px;
  text-align: right;
  color: var(--app-text-muted);
  font-size: 11.5px;
}

.matches-empty {
  padding: 8px 4px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.failed {
  font-size: 12px;
  color: var(--app-text-muted);
  line-height: 1.8;
}

.failed-item {
  margin-right: 8px;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card {
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-bg-subtle);
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.card-rate {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.card .rate {
  margin: 8px 0;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.card details {
  margin-top: 8px;
}

.card summary {
  font-size: 12px;
  color: #8db4ff;
  cursor: pointer;
}

@media (max-width: 768px) {
  .match-time {
    width: auto;
    font-size: 11px;
  }
}
</style>
