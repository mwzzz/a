import { onMounted, onUnmounted, ref } from 'vue'

/** 768px 以下视为手机布局；SSR 不需要，直接读 window。 */
export function useIsMobile() {
  const isMobile = ref(false)
  let media: MediaQueryList | null = null

  const update = () => {
    isMobile.value = media ? media.matches : false
  }

  onMounted(() => {
    media = window.matchMedia('(max-width: 768px)')
    update()
    media.addEventListener('change', update)
  })

  onUnmounted(() => {
    media?.removeEventListener('change', update)
  })

  return isMobile
}
