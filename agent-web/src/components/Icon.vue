<script setup>
defineProps({ name: { type: String, default: 'chat' }, size: { type: Number, default: 20 } })
const paths = {
  home: ['M4 4h6v6H4z', 'M14 4h6v6h-6z', 'M4 14h6v6H4z', 'M14 14h6v6h-6z'],
  history: ['M3 11a9 9 0 1 1 2.7 7', 'M3 5v6h6', 'M12 7v5l3 2'],
  folder: ['M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3Z'],
  globe: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z', 'M16 12a4 9 0 1 1-8 0 4 9 0 0 1 8 0Z', 'M3 12h18'],
  code: ['m7 7-5 5 5 5', 'm17 7 5 5-5 5', 'm14 3-4 18'],
  moon: ['M21 12.8A9 9 0 0 1 11.2 3 9 9 0 1 0 21 12.8Z'],
  sun: ['M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z', 'M12 2v2', 'M12 20v2', 'M2 12h2', 'M20 12h2', 'm4.9 4.9 1.4 1.4', 'm17.7 17.7 1.4 1.4', 'm4.9 19.1 1.4-1.4', 'm17.7 6.3 1.4-1.4'],
  down: ['m6 9 6 6 6-6'],
  diagonal: ['m6 18 12-12', 'M6 6h12v12'],
  sprout: ['M12 22V12', 'M12 16C5 16 2 12 2 5c7 0 10 4 10 11Z', 'M12 12c0-7 3-10 10-10 0 7-3 10-10 10Z'],
  plus: ['M12 5v14', 'M5 12h14'],
  search: ['M21 21l-4.5-4.5', 'M19 10.5a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0'],
  chat: ['M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 4 11.5a8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z'],
  arrow: ['M12 19V5', 'm5 12 7-7 7 7'],
  arrowRight: ['M5 12h14', 'm12 5 7 7-7 7'],
  edit: ['m16 3 5 5', 'm4 15-1 6 6-1L21 8a3.5 3.5 0 0 0-5-5Z'],
  trash: ['M3 6h18', 'M9 6V3h6v3', 'm5 6 1 15h12l1-15', 'M10 10v7', 'M14 10v7'],
  copy: ['M9 9h12v12H9z', 'M5 15H3V3h12v2'],
  book: ['M4 19.5A2.5 2.5 0 0 1 6.5 17H21', 'M6.5 2H21v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z'],
  menu: ['M4 6h16', 'M4 12h16', 'M4 18h16'],
  close: ['m6 6 12 12', 'M6 18 18 6'],
  check: ['m5 12 4 4L19 6'],
  file: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z', 'M14 2v6h6', 'M8 13h8', 'M8 17h5'],
  pen: ['m12 19 7-7 3 3-7 7H2v-4L15 5l4 4', 'm15 5 3-3 4 4-3 3'],
  layers: ['m12 3 10 6-10 6L2 9Z', 'm2 15 10 6 10-6'],
  refresh: ['M20 7v5h-5', 'M4 17v-5h5', 'M6 7a7 7 0 0 1 12-2l2 2', 'm4 17 2 2a7 7 0 0 0 12-2'],
  chevron: ['m9 5 7 7-7 7'],
}
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path v-for="(d, i) in paths[name] || paths.chat" :key="i" :d="d" />
  </svg>
</template>
