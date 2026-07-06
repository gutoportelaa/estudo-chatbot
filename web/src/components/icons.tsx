export function ThinkAILogo({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 784 792"
      aria-hidden
      style={{ display: "block", flexShrink: 0 }}
    >
      <defs>
        <linearGradient id="thinkai-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--theme-gradient-start)" />
          <stop offset="100%" stopColor="var(--theme-gradient-end)" />
        </linearGradient>
      </defs>
      <g transform="matrix(1,0,0,1,-242.34603,-204.815431)">
        <g transform="matrix(3.555556,0,0,3.555556,0,0.000014)">
          <g id="icone" transform="matrix(0.283494,0,0,0.283494,67.471576,56.6988)">
            <path id="face_superior" d="M363.501,366.96C345.879,368.399 335.883,369.715 319.346,378.202C315.933,379.953 309.568,383.84 307.618,385.635C306.058,387.07 301.599,389.274 292.205,399.222C291.265,400.218 288.539,403.907 288.232,404.323C286.445,406.741 285.921,407.35 281.663,405.187C263.87,396.15 263.778,396.511 250.318,389.889C230.882,380.326 169.083,355.568 110.482,351.673C109.383,351.6 109.185,351.05 105.48,350.9C99.735,350.669 98.394,351.064 94.583,350.21C92.322,349.703 50.19,347.96 6.491,355.445C3.469,355.962 4.812,353.615 5.216,344.484C5.244,343.839 5.789,343.983 6.248,336.482C6.321,335.296 14.403,275.271 44.859,215.685C55.005,195.834 78.434,156.333 111.524,121.523C216.923,10.645 347.068,5.495 360.546,3.717C367.478,2.803 406.566,3.242 419.417,3.863C570.542,11.168 622.273,104.954 622.379,105.517C623.186,109.811 615.098,104.81 588.706,118.87C581.763,122.568 574.57,129.401 573.459,130.456C572.835,131.05 570.444,132.26 563.949,139.896C535.582,173.246 537.827,214.138 543.471,230.51C545.967,237.748 544.901,238.166 553.188,254.649C554.936,258.127 552.458,257.928 532.624,277.625C501.665,308.37 501.663,308.315 499.183,311.181C498.516,311.952 498.011,311.373 489.675,319.676C423.312,385.776 423.506,386.827 421.516,386.446C419.512,386.063 420.612,383.918 399.306,373.917C390.649,369.853 382.028,368.878 380.475,368.702C377.338,368.347 377.463,367.861 373.493,367.77C368.459,367.655 368.563,367.132 363.501,366.96Z" fill="url(#thinkai-gradient)" opacity="0.85" />
            <path id="face_inferior_esquerdo" d="M378.493,786.917C366.154,786.835 363.623,786.914 362.473,786.578C357.226,785.045 354.881,786.294 352.472,785.58C347.818,784.199 346.103,785.049 344.475,784.573C340.122,783.304 333.434,782.848 332.465,782.782C331.867,782.741 329.807,781.955 329.45,781.903C324.8,781.225 324.858,780.954 324.453,780.91C320.405,780.464 320.51,780.254 316.456,779.787C313.463,779.442 286.29,772.452 278.413,769.837C257.161,762.781 257.442,762.087 249.61,759.241C248.802,758.947 241.773,756.393 239.646,755.212C228.168,748.839 227.692,749.821 226.77,749.152C222.789,746.266 222.356,747.062 211.29,740.915C201.644,735.556 201.532,735.751 200.778,735.158C200.289,734.774 198.678,733.507 194.267,730.914C192.657,729.968 184.244,725.023 174.654,718.248C166.563,712.533 166.461,712.699 165.796,712.153C165.311,711.754 160.996,708.21 159.655,707.252C152.519,702.156 150.978,700.023 149.241,698.927C146.522,697.211 147.003,696.634 144.24,694.923C139.895,692.233 140.785,691.165 137.237,688.922C135.093,687.566 116.396,669.767 113.808,667.193C110.506,663.908 111.055,663.518 107.789,660.214C95.249,647.531 96.161,646.8 92.804,643.215C92.213,642.584 88.541,638.664 86.073,634.756C83.436,630.581 82.62,631.267 79.865,627.193C76.31,621.936 31.306,564.548 12.784,482.406C10.092,470.466 9.973,470.541 7.974,458.431C7.385,454.865 3.523,431.47 3.13,413.511C2.777,397.387 1.179,395.858 4.442,395.241C5.723,394.999 19.284,392.438 20.483,392.349C38.043,391.041 37.963,390.356 39.491,390.29C54.167,389.653 92.678,385.939 140.559,395.058C148.092,396.493 148.012,396.611 155.562,398.117C165.4,400.078 165.677,400.706 167.573,401.106C177.003,403.1 186.173,406.399 197.584,410.197C213.314,415.433 213.556,416.183 215.681,417.03C232.209,423.617 231.939,424.222 233.382,424.776C236.119,425.828 238.727,426.829 266.327,440.834C272.076,443.752 267.977,446.864 267.771,455.507C267.593,462.958 266.926,462.859 266.942,463.502C267.522,487.78 273.591,500.386 275.209,504.626C277.402,510.373 285.098,523.408 289.182,527.798C294.091,533.075 293.774,533.328 294.205,533.78C298.918,538.732 299.329,538.184 301.612,540.379C304.306,542.968 304.696,542.45 306.618,544.372C310.384,548.135 325.525,555.746 328.387,556.781C356.144,566.82 374.386,562.477 376.476,562.288C379.519,562.012 379.384,561.649 382.468,561.241C393.336,559.801 398.051,554.477 401.204,556.864C403.309,558.458 421.072,588.353 428.23,598.665C428.755,599.422 438.333,614.91 438.687,615.358C442.735,620.478 439.154,621.309 436.254,625.346C430.581,633.246 430.378,633.042 429.93,633.754C405.377,672.797 410.834,723.497 442.647,755.356C458.128,770.86 464.012,771.184 467.228,773.809C471.614,777.391 465.978,779.139 461.531,780.579C451.597,783.796 445.376,783.365 442.407,784.239C438.266,785.458 435.927,784.598 433.437,785.019C426.06,786.267 426.03,786.057 425.407,786.239C420.77,787.595 414.809,786.498 411.444,787.031C407.463,787.661 407.53,787.852 403.501,787.851C390.954,787.848 390.948,788.848 378.493,786.917Z" fill="url(#thinkai-gradient)" opacity="0.3" />
            <path id="face_lateral_direito" d="M604.087,697.483C604.19,690.121 605.08,676.527 601.773,662.403C594.77,632.482 573.419,614.663 573.379,614.623C564.23,605.498 550.621,598.341 547.612,597.233C529.969,590.733 528.061,589.726 513.505,589.829C511.242,589.845 509.013,588.3 505.418,589.249C500.542,590.536 500.357,589.141 495.514,590.543C490.804,591.906 490.542,590.753 477.392,595.23C470.867,597.451 471.282,594.176 465.76,586.337C464.927,585.155 463.754,583.49 455.881,571.201C451.901,564.989 452.132,564.861 451.766,564.336C451.334,563.716 446.707,557.081 446.438,556.538C443.506,550.593 440.333,547.15 439.473,545.517C435.064,537.146 429.816,536.23 436.389,529.397C437.095,528.663 440.905,524.701 444.11,519.275C457.904,495.92 456.728,486.009 458.783,478.59C459.519,475.931 459.298,456.645 458.967,454.439C456.049,434.982 451.565,425.891 448.8,420.35C446.425,415.59 448.569,415.231 464.402,399.402C466.927,396.878 494.327,369.483 496.218,368.112C497.221,367.385 497.373,367.275 507.331,357.33C513.087,351.581 577.494,287.259 579.796,285.979C583.328,284.015 604.528,308.7 653.446,302.1C657.09,301.608 656.842,300.698 660.471,300.25C674.557,298.512 694.796,284.656 696.366,283.339C702.607,278.103 705.12,275.556 705.835,274.831C707.229,273.419 716.032,264.499 721.1,255.283C733.376,232.961 733.877,211.8 734.442,211.407C735.42,210.726 736.36,213.085 737.113,214.696C756.739,256.659 762.376,275.01 770.206,308.598C774.351,326.38 773.434,326.509 776.648,344.478C776.776,345.194 776.838,350.576 777.197,352.585C778.175,358.055 777.188,358.122 778.208,363.586C779.602,371.059 778.577,385.633 779.204,388.581C779.418,389.591 780.738,395.794 779.454,401.488C778.269,406.739 779.354,419.084 778.496,422.499C777.46,426.627 777.91,428.09 777.682,431.521C777.654,431.942 776.98,434.222 776.96,434.539C776.52,441.553 776.267,441.479 775.744,448.523C775.687,449.301 774.968,451.248 774.936,451.555C774.564,455.104 774.442,455.025 773.906,458.557C764.973,517.494 737.552,576.718 712.24,612.337C711.65,613.167 705.429,621.922 704.922,622.745C702.206,627.158 685.268,648.025 684.648,648.642C680.435,652.839 681.006,653.281 677.636,656.635C668.767,665.462 668.897,666.518 663.211,672.211C658.927,676.5 658.497,675.974 654.213,680.21C631.793,702.374 604.097,720.726 603.7,720.953C597.406,724.544 601.074,717.946 604.087,697.483Z" fill="url(#thinkai-gradient)" opacity="0.6" />
            <path id="bola_3" d="M574.09,194.445C575.397,185.425 576.082,185.46 578.047,180.337C578.638,178.794 582.444,168.873 588.567,162.56C589.867,161.22 599.045,151.757 606.69,147.876C650.613,125.578 690.084,152.986 700.051,187.654C703.967,201.274 701.403,214.342 700.956,216.617C693.002,257.152 652.376,277.527 618.547,266.368C592.502,257.777 568.534,232.083 574.09,194.445Z" fill="var(--theme-gradient-start)" opacity="1" />
            <path id="bola_2" d="M357.465,402.048C375.564,399.428 400.095,406.738 414.911,427.208C417.726,431.098 417.379,431.237 419.961,435.225C427.878,447.451 428.574,468.715 426.325,478.45C416.382,521.477 371.877,540.997 335.736,523.039C314.543,512.509 304.08,491.542 301.705,480.438C292.92,439.364 321.335,404.763 357.465,402.048Z" fill="var(--theme-gradient-start)" opacity="1" />
            <path id="bola_1" d="M509.501,623.051C546.571,621.968 579.793,656.616 571.817,698.549C562.72,746.378 502.76,769.682 463.535,729.466C447.596,713.124 433.869,671.781 467.462,639.46C483.786,623.754 503.089,623.175 506.473,623.074C507.482,623.043 508.492,623.082 509.501,623.051Z" fill="var(--theme-gradient-start)" opacity="1" />
          </g>
        </g>
      </g>
    </svg>
  );
}

export function LogoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 4v16" stroke="currentColor" strokeWidth="1.8" />
      <path d="M7 9h2M7 13h2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function RefreshIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M21 12a9 9 0 1 1-2.6-6.3M21 4v4h-4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 12h14M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ImageIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="8.5" cy="9.5" r="1.5" fill="currentColor" />
      <path d="M21 16l-5-5-7 7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function ChatIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

export function EllipsisIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M6 12h.01M12 12h.01M18 12h.01" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" />
    </svg>
  );
}

export function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 6h18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6 6l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M10 11v5M14 11v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function PaperclipIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M21 11.5l-8.5 8.5a5 5 0 0 1-7-7L14 4.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.3-2.3l7.8-7.8"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SettingsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function BookIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function QuoteIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M7 7h4v6a4 4 0 0 1-4 4M13 7h4v6a4 4 0 0 1-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function HomeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 10.5 12 3l9 7.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 9.5V20h5v-6h4v6h5V9.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function UserIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="8" r="4" stroke="currentColor" strokeWidth="2" />
      <path d="M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function GlobeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
      <path d="M3 12h18M12 3c2.5 2.5 2.5 15 0 18M12 3c-2.5 2.5-2.5 15 0 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ChartIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 3v18h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <rect x="7" y="12" width="3" height="5" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <rect x="13" y="8" width="3" height="9" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  );
}
