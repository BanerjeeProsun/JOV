import React, { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion, useInView } from 'motion/react'
import { useTheme } from '../ThemeProvider'

interface HeroVideoProps {
  className?: string
}

export const HeroVideo: React.FC<HeroVideoProps> = ({ className = '' }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [canPlay, setCanPlay] = useState(false)
  const [mounted, setMounted] = useState(false)
  const reducedMotion = useReducedMotion()
  const isInView = useInView(containerRef, { amount: 0.1 })
  const { resolvedTheme } = useTheme()

  const isDark = resolvedTheme === 'dark'

  // Reset playback state on theme change
  useEffect(() => {
    setCanPlay(false)
  }, [isDark])

  // Mount video quickly
  useEffect(() => {
    if (reducedMotion) return
    setMounted(true)
  }, [reducedMotion])

  // If already buffered, mark as ready to play immediately
  useEffect(() => {
    if (videoRef.current && videoRef.current.readyState >= 2) {
      setCanPlay(true)
    }
  }, [mounted, isDark])

  // Play/pause based on viewport visibility to conserve GPU
  useEffect(() => {
    if (!videoRef.current || reducedMotion) return
    if (isInView && document.visibilityState === 'visible') {
      videoRef.current.play().catch(() => {})
    } else {
      videoRef.current.pause()
    }
  }, [isInView, mounted, reducedMotion, isDark])

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
  }, [isInView, reducedMotion, isDark])

  // Multi-directional feathering mask:
  // Tight ellipse that guarantees all 4 outer edges (top, bottom, left, right)
  // fade to 100% transparent well before reaching the rectangular video bounds.
  // This eliminates any visible rectangular seams or cut-off borders.
  const maskStyle: React.CSSProperties = {
    maskImage:
      'radial-gradient(ellipse 48% 46% at 50% 50%, black 15%, rgba(0, 0, 0, 0.85) 42%, rgba(0, 0, 0, 0.2) 68%, transparent 92%)',
    WebkitMaskImage:
      'radial-gradient(ellipse 48% 46% at 50% 50%, black 15%, rgba(0, 0, 0, 0.85) 42%, rgba(0, 0, 0, 0.2) 68%, transparent 92%)',
  }

  const videoSrc = isDark ? '/media/hero-video.mp4' : '/media/hero-video-light.mp4'
  const posterSrc = isDark ? '/media/hero-poster.jpg' : '/media/hero-poster-light.jpg'

  return (
    <div
      ref={containerRef}
      className={`relative w-full aspect-[16/10] max-w-[640px] xl:max-w-[720px] flex items-center justify-center overflow-hidden pointer-events-none select-none ${className}`}
      aria-hidden="true"
    >
      {/* Soft atmospheric light glow behind the video matching the theme */}
      <div
        className="absolute inset-0 pointer-events-none opacity-45 blur-[85px]"
        style={{
          background: isDark
            ? 'radial-gradient(ellipse at 50% 50%, rgba(56, 189, 248, 0.14) 0%, rgba(99, 102, 241, 0.08) 45%, transparent 75%)'
            : 'radial-gradient(ellipse at 50% 50%, rgba(225, 210, 255, 0.35) 0%, rgba(255, 225, 205, 0.25) 45%, transparent 75%)',
        }}
      />

      <div
        className="absolute inset-0 w-full h-full flex items-center justify-center"
        style={maskStyle}
      >
        {/* High-fidelity fallback / poster image */}
        <img
          key={isDark ? 'poster-dark' : 'poster-light'}
          src={posterSrc}
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-700"
          style={{
            opacity: canPlay ? 0 : 0.95,
            filter: isDark ? 'brightness(1.02) contrast(1.04)' : 'brightness(1.0) contrast(1.02)',
          }}
        />

        {/* Real video layer */}
        {mounted && !reducedMotion && (
          <motion.video
            key={isDark ? 'video-dark' : 'video-light'}
            ref={videoRef}
            muted
            loop
            playsInline
            autoPlay
            preload="auto"
            onLoadedData={() => setCanPlay(true)}
            onCanPlay={() => setCanPlay(true)}
            onPlaying={() => setCanPlay(true)}
            initial={{ opacity: 0 }}
            animate={{
              opacity: canPlay ? 0.95 : 0,
            }}
            transition={{ duration: 0.6 }}
            className="absolute inset-0 w-full h-full object-cover"
            style={{
              filter: isDark ? 'brightness(1.02) contrast(1.05)' : 'brightness(1.0) contrast(1.02)',
            }}
          >
            <source src={videoSrc} type="video/mp4" />
          </motion.video>
        )}
      </div>
    </div>
  )
}
