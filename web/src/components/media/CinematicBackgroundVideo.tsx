import React, { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion, useInView } from 'motion/react'
import { useTheme } from '../ThemeProvider'

interface CinematicBackgroundVideoProps {
  className?: string
}

export const CinematicBackgroundVideo: React.FC<CinematicBackgroundVideoProps> = ({
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [mounted, setMounted] = useState(false)
  const [canPlay, setCanPlay] = useState(false)
  const reducedMotion = useReducedMotion()
  const isInView = useInView(containerRef, { amount: 0.1 })
  const { resolvedTheme } = useTheme()

  // Defer video mounting to avoid blocking initial render
  useEffect(() => {
    if (reducedMotion) return
    const handle = (window as any).requestIdleCallback
      ? (window as any).requestIdleCallback(() => setMounted(true))
      : setTimeout(() => setMounted(true), 200)

    return () => {
      if ((window as any).cancelIdleCallback && typeof handle === 'number') {
        ;(window as any).cancelIdleCallback(handle)
      } else {
        clearTimeout(handle)
      }
    }
  }, [reducedMotion])

  // Pause video when off screen or tab is hidden to preserve GPU/battery
  useEffect(() => {
    if (!videoRef.current || reducedMotion) return
    if (isInView && document.visibilityState === 'visible') {
      videoRef.current.play().catch(() => {})
    } else {
      videoRef.current.pause()
    }
  }, [isInView, mounted, reducedMotion])

  useEffect(() => {
    const handleVisibility = () => {
      if (!videoRef.current || reducedMotion) return
      if (document.visibilityState === 'visible' && isInView) {
        videoRef.current.play().catch(() => {})
      } else {
        videoRef.current.pause()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [isInView, reducedMotion])

  return (
    <div
      ref={containerRef}
      className={`absolute inset-0 overflow-hidden pointer-events-none select-none z-0 ${className}`}
      aria-hidden="true"
    >
      {/* Poster image: always displayed initially */}
      <img
        src="/media/onboarding-poster.jpg"
        alt=""
        className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-700 ${
          canPlay ? 'opacity-0' : 'opacity-100'
        }`}
      />

      {/* Video layer (deferred mount) */}
      {mounted && !reducedMotion && (
        <motion.video
          ref={videoRef}
          muted
          loop
          playsInline
          preload="metadata"
          onCanPlay={() => setCanPlay(true)}
          initial={{ opacity: 0 }}
          animate={{ opacity: canPlay ? 1 : 0 }}
          transition={{ duration: 0.8 }}
          className="absolute inset-0 w-full h-full object-cover"
        >
          <source src="/media/onboarding-loop.webm" type="video/webm" />
          <source src="/media/onboarding-loop.mp4" type="video/mp4" />
        </motion.video>
      )}

      {/* Theme-aware scrim overlay ensuring >= 4.5:1 text contrast */}
      <div
        className="absolute inset-0"
        style={{
          background:
            resolvedTheme === 'dark'
              ? 'linear-gradient(to right, rgba(5,5,6,0.92) 0%, rgba(5,5,6,0.78) 45%, rgba(5,5,6,0.85) 100%), linear-gradient(to bottom, rgba(5,5,6,0.6) 0%, transparent 35%, rgba(5,5,6,0.95) 100%)'
              : 'linear-gradient(to right, rgba(251,251,253,0.94) 0%, rgba(251,251,253,0.82) 45%, rgba(251,251,253,0.88) 100%), linear-gradient(to bottom, rgba(251,251,253,0.7) 0%, transparent 35%, rgba(251,251,253,0.95) 100%)',
          mixBlendMode: resolvedTheme === 'dark' ? 'normal' : 'multiply',
        }}
      />
    </div>
  )
}
