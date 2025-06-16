#!/usr/bin/env python3
"""
Data Exporter for Google My Maps
CSV/KML 파일 생성 및 내보내기
"""

import pandas as pd
import simplekml
from pathlib import Path
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class DataExporter:
    def __init__(self, processor):
        """
        데이터 내보내기 클래스 초기화

        Args:
            processor: PhotoExifProcessor 인스턴스
        """
        self.processor = processor
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)

    def prepare_export_data(self):
        """
        내보내기용 데이터 준비 (order 컬럼 추가 및 정렬)
        """
        if self.processor.df.empty:
            raise ValueError("내보낼 데이터가 없습니다. 먼저 EXIF 처리를 완료해주세요.")

        # 완전한 데이터만 필터링 (날짜와 GPS 모두 있는 것)
        export_df = self.processor.df[
            (self.processor.df["DateTimeOriginal"].notna())
            & (self.processor.df["GPSLat"].notna())
            & (self.processor.df["GPSLong"].notna())
        ].copy()

        if export_df.empty:
            raise ValueError("내보낼 수 있는 완전한 데이터가 없습니다.")

        # datetime 컬럼이 없으면 생성
        if "datetime" not in export_df.columns:
            export_df["datetime"] = pd.to_datetime(
                export_df["DateTimeOriginal"], errors="coerce"
            )

        # chunk_id가 없으면 재생성
        if "chunk_id" not in export_df.columns or export_df["chunk_id"].isna().all():
            self.processor.detect_date_chunks()
            export_df = self.processor.df[
                (self.processor.df["DateTimeOriginal"].notna())
                & (self.processor.df["GPSLat"].notna())
                & (self.processor.df["GPSLong"].notna())
            ].copy()

        # order 컬럼 추가
        export_df["order"] = export_df.groupby("chunk_id")["datetime"].rank(
            method="dense", ascending=True
        )
        export_df["order"] = export_df["order"].astype(int)

        # 정렬
        export_df = export_df.sort_values(["chunk_id", "order"])

        logger.info(
            f"내보내기 준비 완료: {len(export_df)}개 파일, {export_df['chunk_id'].nunique()}개 덩어리"
        )
        return export_df

    def export_csv(self, filename=None):
        """
        CSV 파일로 내보내기

        Args:
            filename: 출력 파일명 (None이면 자동 생성)

        Returns:
            str: 생성된 파일 경로
        """
        export_df = self.prepare_export_data()

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_exif_export_{timestamp}.csv"

        output_path = self.output_dir / filename

        # Google My Maps용 컬럼 매핑
        csv_df = export_df[
            [
                "FileName",
                "DateTimeOriginal",
                "GPSLat",
                "GPSLong",
                "chunk_id",
                "order",
                "FilePath",
            ]
        ].copy()

        # Google My Maps에서 인식하기 좋은 컬럼명으로 변경
        csv_df = csv_df.rename(
            columns={
                "FileName": "파일명",
                "DateTimeOriginal": "촬영일시",
                "GPSLat": "위도",
                "GPSLong": "경도",
                "chunk_id": "날짜그룹",
                "order": "순서",
                "FilePath": "파일경로",
            }
        )

        # CSV 저장
        csv_df.to_csv(output_path, index=False, encoding="utf-8-sig")

        logger.info(f"CSV 파일 내보내기 완료: {output_path}")
        return str(output_path)

    def export_kml(self, filename=None):
        """
        KML 파일로 내보내기 (Google Earth/My Maps용)

        Args:
            filename: 출력 파일명 (None이면 자동 생성)

        Returns:
            str: 생성된 파일 경로
        """
        export_df = self.prepare_export_data()

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"photo_exif_export_{timestamp}.kml"

        output_path = self.output_dir / filename

        # KML 객체 생성
        kml = simplekml.Kml()
        kml.document.name = "사진 위치 정보"
        kml.document.description = f"총 {len(export_df)}개 사진의 위치 정보 (생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"

        # chunk_id별로 폴더 생성
        for chunk_id, chunk_df in export_df.groupby("chunk_id"):
            # 날짜 범위 계산
            start_date = chunk_df["datetime"].min().strftime("%Y-%m-%d")
            end_date = chunk_df["datetime"].max().strftime("%Y-%m-%d")

            if start_date == end_date:
                folder_name = f"{chunk_id} ({start_date})"
            else:
                folder_name = f"{chunk_id} ({start_date} ~ {end_date})"

            folder = kml.newfolder(name=folder_name)
            folder.description = f"{len(chunk_df)}개 사진"

            # chunk 내에서 순서대로 포인트 추가
            for _, row in chunk_df.sort_values("order").iterrows():
                point = folder.newpoint()
                point.name = f"{row['order']:02d}. {row['FileName']}"
                point.coords = [(row["GPSLong"], row["GPSLat"])]

                # 상세 정보
                point.description = f"""
<b>파일명:</b> {row['FileName']}<br>
<b>촬영일시:</b> {row['DateTimeOriginal']}<br>
<b>위치:</b> {row['GPSLat']:.6f}, {row['GPSLong']:.6f}<br>
<b>순서:</b> {row['order']}/{len(chunk_df)}<br>
<b>그룹:</b> {chunk_id}
"""

                # 스타일 설정 (순서에 따른 색상)
                if row["order"] == 1:
                    # 첫 번째: 녹색
                    point.style.iconstyle.icon.href = (
                        "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png"
                    )
                elif row["order"] == len(chunk_df):
                    # 마지막: 빨간색
                    point.style.iconstyle.icon.href = (
                        "http://maps.google.com/mapfiles/kml/paddle/red-circle.png"
                    )
                else:
                    # 중간: 파란색
                    point.style.iconstyle.icon.href = (
                        "http://maps.google.com/mapfiles/kml/paddle/blu-circle.png"
                    )

                point.style.iconstyle.scale = 1.2

        # KML 저장
        kml.save(str(output_path))

        logger.info(f"KML 파일 내보내기 완료: {output_path}")
        return str(output_path)

    def export_chunk_separated_csv(self):
        """
        chunk_id별로 분리된 CSV 파일들 생성

        Returns:
            list: 생성된 파일 경로들
        """
        export_df = self.prepare_export_data()
        output_files = []

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for chunk_id, chunk_df in export_df.groupby("chunk_id"):
            filename = f"photo_exif_{chunk_id}_{timestamp}.csv"
            output_path = self.output_dir / filename

            # 해당 chunk 데이터만 정렬하여 저장
            chunk_csv = chunk_df.sort_values("order")[
                ["FileName", "DateTimeOriginal", "GPSLat", "GPSLong", "order"]
            ].copy()

            # 컬럼명 변경
            chunk_csv = chunk_csv.rename(
                columns={
                    "FileName": "파일명",
                    "DateTimeOriginal": "촬영일시",
                    "GPSLat": "위도",
                    "GPSLong": "경도",
                    "order": "순서",
                }
            )

            chunk_csv.to_csv(output_path, index=False, encoding="utf-8-sig")
            output_files.append(str(output_path))

            logger.info(
                f"Chunk {chunk_id} CSV 생성: {output_path} ({len(chunk_csv)}개 파일)"
            )

        return output_files

    def create_google_my_maps_guide(self):
        """
        Google My Maps 업로드 가이드 텍스트 파일 생성
        """
        guide_path = self.output_dir / "Google_My_Maps_업로드_가이드.txt"

        guide_content = (
            """
=== Google My Maps 업로드 가이드 ===

1. Google My Maps 접속
   - https://mymaps.google.com 에 접속
   - Google 계정으로 로그인

2. 새 지도 생성
   - "새 지도 만들기" 클릭
   - 지도 제목 입력 (예: "여행 사진 위치")

3. 레이어별 CSV 업로드 방법

   방법 1: 통합 CSV 사용
   - 생성된 "photo_exif_export_*.csv" 파일 업로드
   - "레이어 추가" → "가져오기" → CSV 파일 선택
   - 위도/경도 컬럼 매핑: "위도", "경도" 선택
   - 제목 필드: "순서" 또는 "파일명" 선택
   - 업로드 후 "날짜그룹"으로 스타일 분류

   방법 2: 날짜별 분리 CSV 사용
   - 각 "photo_exif_[날짜그룹]_*.csv" 파일을 별도 레이어로 업로드
   - 레이어 이름을 날짜그룹 이름으로 설정
   - 각 레이어별로 다른 색상/아이콘 설정 가능

4. KML 파일 사용 (선택사항)
   - Google Earth에서 "photo_exif_export_*.kml" 파일 열기
   - 또는 Google My Maps에서 KML 가져오기

5. 지도 스타일링
   - 각 레이어별 색상/아이콘 변경
   - 순서대로 연결선 추가 (선택사항)
   - 범례 추가

6. 지도 공유
   - "공유" 버튼으로 링크 생성
   - 권한 설정 (보기/편집)

=== 참고사항 ===
- 한 번에 업로드 가능한 포인트: 최대 2,000개
- 파일 크기 제한: 5MB
- 지원 형식: CSV, KML, GPX, XLSX

생성 시간: """
            + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            + """
"""
        )

        with open(guide_path, "w", encoding="utf-8") as f:
            f.write(guide_content)

        logger.info(f"Google My Maps 가이드 생성: {guide_path}")
        return str(guide_path)

    def export_all(self):
        """
        모든 형식으로 내보내기 (CSV, KML, 가이드)

        Returns:
            dict: 생성된 파일들의 경로
        """
        results = {}

        try:
            # 통합 CSV
            results["csv"] = self.export_csv()

            # KML
            results["kml"] = self.export_kml()

            # 분리된 CSV들
            results["chunk_csvs"] = self.export_chunk_separated_csv()

            # 가이드
            results["guide"] = self.create_google_my_maps_guide()

            # 요약 파일 생성
            summary_path = self.create_export_summary(results)
            results["summary"] = summary_path

            logger.info("모든 파일 내보내기 완료!")
            return results

        except Exception as e:
            logger.error(f"내보내기 중 오류 발생: {e}")
            raise

    def create_export_summary(self, results):
        """
        내보내기 결과 요약 파일 생성
        """
        summary_path = self.output_dir / "내보내기_요약.txt"
        export_df = self.prepare_export_data()

        summary_content = f"""
=== 사진 EXIF 데이터 내보내기 요약 ===

생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

== 처리 결과 ==
- 전체 사진 수: {len(self.processor.df)}개
- 내보낸 사진 수: {len(export_df)}개
- 날짜 덩어리 수: {export_df['chunk_id'].nunique()}개

== 날짜 덩어리별 상세 ==
"""

        for chunk_id, chunk_df in export_df.groupby("chunk_id"):
            start_date = chunk_df["datetime"].min().strftime("%Y-%m-%d")
            end_date = chunk_df["datetime"].max().strftime("%Y-%m-%d")
            date_range = (
                start_date if start_date == end_date else f"{start_date} ~ {end_date}"
            )

            summary_content += f"- {chunk_id}: {len(chunk_df)}개 사진 ({date_range})\n"

        summary_content += f"""

== 생성된 파일 ==
- 통합 CSV: {Path(results['csv']).name}
- KML 파일: {Path(results['kml']).name}
- 분리 CSV: {len(results['chunk_csvs'])}개 파일
- 업로드 가이드: {Path(results['guide']).name}

== 다음 단계 ==
1. Google My Maps (https://mymaps.google.com) 접속
2. 새 지도 생성
3. CSV 또는 KML 파일 업로드
4. 업로드 가이드 참조하여 지도 설정

모든 파일은 'output' 폴더에 저장되었습니다.
"""

        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_content)

        logger.info(f"내보내기 요약 생성: {summary_path}")
        return str(summary_path)
