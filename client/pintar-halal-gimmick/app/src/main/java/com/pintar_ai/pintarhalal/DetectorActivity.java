/*
 * Copyright 2019 The TensorFlow Authors. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.pintar_ai.pintarhalal;

import android.Manifest;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Bitmap.Config;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Paint.Style;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.media.ImageReader.OnImageAvailableListener;
import android.os.Handler;
import android.os.SystemClock;
import android.util.Size;
import android.util.TypedValue;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Switch;
import android.widget.Toast;

import com.google.android.gms.tasks.OnSuccessListener;
import com.google.android.gms.tasks.Task;
import com.google.mlkit.vision.common.InputImage;
import com.pintar_ai.pintarhalal.customview.OverlayView;
import com.pintar_ai.pintarhalal.customview.OverlayView.DrawCallback;
import com.pintar_ai.pintarhalal.env.BorderedText;
import com.pintar_ai.pintarhalal.env.ImageUtils;
import com.pintar_ai.pintarhalal.env.Logger;
import com.pintar_ai.pintarhalal.tflite.Classifier;
import com.pintar_ai.pintarhalal.tflite.TFLiteObjectDetectionAPIModel;
import com.pintar_ai.pintarhalal.tracking.MultiBoxTracker;

import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;

import static android.Manifest.permission.ACCESS_COARSE_LOCATION;
import static android.Manifest.permission.ACCESS_FINE_LOCATION;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationListener;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationResult;
import com.google.android.gms.location.LocationServices;

import android.location.Location;

import androidx.core.app.ActivityCompat;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Hashtable;
import java.util.LinkedList;
import java.util.List;
import java.util.Queue;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * An activity that uses a TensorFlowMultiBoxDetector and ObjectTracker to detect and then track
 * objects.
 */
public class DetectorActivity extends CameraActivity implements OnImageAvailableListener {
  private static final Logger LOGGER = new Logger();

  //OCR
  private final TextRecognizer textRecognizer = TextRecognition.getClient();
  private final AtomicReference<String> serial_num = new AtomicReference<>();
  private final AtomicReference<String> reference = new AtomicReference<>();
  private final Hashtable<String, String> serial_product = new Hashtable<String, String>();
  private final Hashtable<String, String> cached_product = new Hashtable<String, String>();
  private long idle_time = 0;
  private long detect_time = 0;

  //GPS
  /*
  private final FusedLocationProviderClient mFusedLocationClient = LocationServices.getFusedLocationProviderClient(this);
  private LocationCallback locationCallback;
  private LocationRequest locationRequest = LocationRequest.create();
  private double phoneLatitude = 0;
  private double phoneLongitude = 0;
   */

  //Gimmick
  private boolean gimmick_trigger = false;
  private long send_gimmick_time = 0;

  // Configuration values for the prepackaged SSD model.
  private static final int TF_OD_API_INPUT_SIZE = 300;
  private static final boolean TF_OD_API_IS_QUANTIZED = false;
  private static final String TF_OD_API_MODEL_FILE = "halal_model.tflite";
  private static final String TF_OD_API_LABELS_FILE = "file:///android_asset/halal_labelmap.txt";
  private static final DetectorMode MODE = DetectorMode.TF_OD_API;
  // Minimum detection confidence to track a detection.
  private static final float MINIMUM_CONFIDENCE_TF_OD_API = 0.85f;
  private static final boolean MAINTAIN_ASPECT = false;
  private static final Size DESIRED_PREVIEW_SIZE = new Size(640, 480);
  private static final boolean SAVE_PREVIEW_BITMAP = false;
  private static final float TEXT_SIZE_DIP = 10;
  OverlayView trackingOverlay;
  private Integer sensorOrientation;

  private Classifier detector;

  private long lastProcessingTimeMs;
  private Bitmap rgbFrameBitmap = null;
  private Bitmap croppedBitmap = null;
  private Bitmap cropCopyBitmap = null;

  private boolean computingDetection = false;

  private long timestamp = 0;

  private Matrix frameToCropTransform;
  private Matrix cropToFrameTransform;

  private MultiBoxTracker tracker;

  private BorderedText borderedText;

  @Override
  public void onPreviewSizeChosen(final Size size, final int rotation) {
    final float textSizePx =
            TypedValue.applyDimension(
                    TypedValue.COMPLEX_UNIT_DIP, TEXT_SIZE_DIP, getResources().getDisplayMetrics());
    borderedText = new BorderedText(textSizePx);
    borderedText.setTypeface(Typeface.MONOSPACE);

    tracker = new MultiBoxTracker(this);

    int cropSize = TF_OD_API_INPUT_SIZE;

    try {
      detector =
              TFLiteObjectDetectionAPIModel.create(
                      getAssets(),
                      TF_OD_API_MODEL_FILE,
                      TF_OD_API_LABELS_FILE,
                      TF_OD_API_INPUT_SIZE,
                      TF_OD_API_IS_QUANTIZED);
      cropSize = TF_OD_API_INPUT_SIZE;
    } catch (final IOException e) {
      e.printStackTrace();
      LOGGER.e(e, "Exception initializing classifier!");
      Toast toast =
              Toast.makeText(
                      getApplicationContext(), "Classifier could not be initialized", Toast.LENGTH_SHORT);
      toast.show();
      finish();
    }

    previewWidth = size.getWidth();
    previewHeight = size.getHeight();

    sensorOrientation = rotation - getScreenOrientation();
    LOGGER.i("Camera orientation relative to screen canvas: %d", sensorOrientation);

    LOGGER.i("Initializing at size %dx%d", previewWidth, previewHeight);
    rgbFrameBitmap = Bitmap.createBitmap(previewWidth, previewHeight, Config.ARGB_8888);
    croppedBitmap = Bitmap.createBitmap(cropSize, cropSize, Config.ARGB_8888);

    frameToCropTransform =
            ImageUtils.getTransformationMatrix(
                    previewWidth, previewHeight,
                    cropSize, cropSize,
                    sensorOrientation, MAINTAIN_ASPECT);

    cropToFrameTransform = new Matrix();
    frameToCropTransform.invert(cropToFrameTransform);

    trackingOverlay = (OverlayView) findViewById(R.id.tracking_overlay);
    trackingOverlay.addCallback(
            new DrawCallback() {
              @Override
              public void drawCallback(final Canvas canvas) {
                tracker.draw(canvas);
                if (isDebug()) {
                  tracker.drawDebug(canvas);
                }
              }
            });

    tracker.setFrameConfiguration(previewWidth, previewHeight, sensorOrientation);
  }

  @Override
  protected void processImage() {
    EditText gimmick_server = (EditText)findViewById(R.id.server_info);
    Button trigger_button = (Button)findViewById(R.id.trigger_button);
    Switch switch_trigger = (Switch)findViewById(R.id.switch_trigger);
    ++timestamp;
    final long currTimestamp = timestamp;
    trackingOverlay.postInvalidate();

    // No mutex needed as this method is not reentrant.
    if (computingDetection) {
      readyForNextImage();
      return;
    }
    computingDetection = true;
    LOGGER.i("Preparing image " + currTimestamp + " for detection in bg thread.");

    rgbFrameBitmap.setPixels(getRgbBytes(), 0, previewWidth, 0, 0, previewWidth, previewHeight);

    readyForNextImage();

    final Canvas canvas = new Canvas(croppedBitmap);
    canvas.drawBitmap(rgbFrameBitmap, frameToCropTransform, null);
    // For examining the actual TF input.
    if (SAVE_PREVIEW_BITMAP) {
      ImageUtils.saveBitmap(croppedBitmap);
    }
    /*
    if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED && ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
      // TODO: Consider calling
      //    ActivityCompat#requestPermissions
      // here to request the missing permissions, and then overriding
      //   public void onRequestPermissionsResult(int requestCode, String[] permissions,
      //                                          int[] grantResults)
      // to handle the case where the user grants the permission. See the documentation
      // for ActivityCompat#requestPermissions for more details.
      return;
    }
    mFusedLocationClient.getLastLocation().addOnSuccessListener(this, location -> {
      if (location != null) {
        phoneLatitude = location.getLatitude();
        phoneLongitude = location.getLongitude();
        LOGGER.i("Location", "Latitude " + phoneLatitude + "\n");
        LOGGER.i("Location", "Longitude " + phoneLongitude + "\n");
      }
    });
    */

    Boolean send_gimmick = switch_trigger.isChecked();
    String gimmick_ip = gimmick_server.getText().toString();

    trigger_button.setOnClickListener(
            new View.OnClickListener()
            {
              public void onClick(View view)
              {
                gimmick_trigger = true;
              }
            });

    runInBackground(
            new Runnable() {
              private ServerConn serverconnect = new ServerConn("178.128.52.9:5000");

              @Override
              public void run() {
                LOGGER.i("Running detection on image " + currTimestamp);
                final long startTime = SystemClock.uptimeMillis();
                final List<Classifier.Recognition> results = detector.recognizeImage(croppedBitmap);
                //final Task<Text> ocr_results = textRecognizer.process(InputImage.fromBitmap(croppedBitmap, 0));
                //ocr_results.addOnSuccessListener(text -> LOGGER.i("On-device Text detection successful " + text.getText ()));
                lastProcessingTimeMs = SystemClock.uptimeMillis() - startTime;

                cropCopyBitmap = Bitmap.createBitmap(croppedBitmap);
                final Canvas canvas = new Canvas(cropCopyBitmap);
                final Paint paint = new Paint();
                paint.setColor(Color.RED);
                paint.setStyle(Style.STROKE);
                paint.setStrokeWidth(2.0f);

                float minimumConfidence = MINIMUM_CONFIDENCE_TF_OD_API;
                switch (MODE) {
                  case TF_OD_API:
                    minimumConfidence = MINIMUM_CONFIDENCE_TF_OD_API;
                    break;
                }

                final List<Classifier.Recognition> mappedRecognitions =
                        new LinkedList<Classifier.Recognition>();

                if (gimmick_trigger && send_gimmick){
                  LOGGER.i("Fetch product detail to server ");
                  List<String> gimmick_response = serverconnect.RequestGimmick(gimmick_ip);
                  LOGGER.i("Get response from server " + gimmick_response);
                  gimmick_trigger = false;
                }

                for (final Classifier.Recognition result : results) {
                  final RectF location = result.getLocation();
                  if (location != null && result.getConfidence() >= minimumConfidence) {
                    // Send to gimmick server that halal logo is detected
                    idle_time = SystemClock.uptimeMillis() - send_gimmick_time;
                    if (idle_time > 2000 && send_gimmick){
                      LOGGER.i("Fetch product detail to server ");
                      List<String> gimmick_response = serverconnect.RequestGimmick(gimmick_ip);
                      LOGGER.i("Get response from server " + gimmick_response);
                      send_gimmick_time = SystemClock.uptimeMillis();
                    }


                    detect_time = SystemClock.uptimeMillis();
                    // Calculate OCR box
                    float ocr_width = (float) (location.width() * 1.8);
                    float ocr_height = (float) (location.height() * 0.6);
                    float ocr_top = location.bottom;
                    float ocr_left = location.left - ((ocr_width - location.width()) / 2);
                    float ocr_right = location.right + ((ocr_width - location.width()) / 2);
                    float ocr_bottom = location.bottom + ocr_height;
                    RectF ocr_box = new RectF(ocr_left, ocr_top, ocr_right, ocr_bottom);

                    // Draw OCR box
                    canvas.drawRect(ocr_box, paint);
                    cropToFrameTransform.mapRect(ocr_box);
                    int crop_height;
                    int crop_width;
                    int crop_X;
                    int crop_Y;
                    if ((ocr_box.top + ocr_box.height()) > rgbFrameBitmap.getHeight()) {
                      crop_height = (int) (rgbFrameBitmap.getHeight() - ocr_box.top);
                    } else {
                      crop_height = (int) ocr_box.height();
                    }

                    if ((ocr_box.left + ocr_box.width()) > rgbFrameBitmap.getWidth()) {
                      crop_width = (int) (rgbFrameBitmap.getWidth() - ocr_box.left);
                    } else {
                      crop_width = (int) ocr_box.width();
                    }

                    if (ocr_box.left < 0) {
                      crop_X = 0;
                    } else {
                      crop_X = (int) ocr_box.left;
                    }

                    if (ocr_box.top < 0) {
                      crop_Y = 0;
                    } else {
                      crop_Y = (int) ocr_box.top;
                    }
                    Bitmap ocr_bitmap;
                    try {
                      ocr_bitmap = Bitmap.createBitmap(rgbFrameBitmap, crop_X, crop_Y, crop_width, crop_height);
                    } catch (Exception e) {
                      System.out.println(e.getMessage());
                      Bitmap.Config conf = Bitmap.Config.ARGB_8888;
                      ocr_bitmap = Bitmap.createBitmap(10, 10, conf);
                    }
                    final Task<Text> ocr_results = textRecognizer.process(InputImage.fromBitmap(ocr_bitmap, 90));
                    ocr_results.addOnSuccessListener(text -> {
                      LOGGER.i("On-device Text detection successful " + text.getText());
                      String[] texts = text.getText().split("\n");
                      for (String line_text : texts) {
                        // Categorized Halal product by serial number
                        if (line_text.contains("MS 1500")) {
                          serial_product.put("ms_code", "MS 1500:2009");
                          serial_product.put("description", "Halal Food/drink");
                        } else if (line_text.contains("MS 2200")) {
                          serial_product.put("ms_code", "MS 2200 Part 1:2008");
                          serial_product.put("description", "Halal Cosmetic");
                        } else if (line_text.contains("MS 2400-1")) {
                          serial_product.put("ms_code", "MS 2400-1:2010 (P)");
                          serial_product.put("description", "Halal Cargo");
                        } else if (line_text.contains("MS 2400-2")) {
                          serial_product.put("ms_code", "MS 2400-2:2010 (P)");
                          serial_product.put("description", "Halal Warehouse");
                        } else if (line_text.contains("MS 2400-3")) {
                          serial_product.put("ms_code", "MS 2400-3:2010 (P)");
                          serial_product.put("description", "Halal Retail");
                        }

                        // Filter reference number
                        Pattern p = Pattern.compile("\\d{4}-\\d{2}\\/\\d{4}");
                        Matcher m = p.matcher(line_text);
                        if (m.find()) {
                          serial_product.put("reference", m.group(0));
                        }
                      }
                    });

                //ImageUtils.saveBitmap(ocr_bitmap);
                // Check if new reading is already queried to the server
                if (serial_product.get("ms_code")==cached_product.get("ms_code") && serial_product.get("reference")==cached_product.get("reference") && serial_product.get("ms_code")!=null){
                  LOGGER.i("Product already checked");
                }else if(serial_product.get("ms_code")!=null && serial_product.get("reference")!=null){
                  // Fetch to server
                  LOGGER.i("Fetch product detail to server ");
                  List<String> response = serverconnect.RequestItem(serial_product.get("ms_code"), serial_product.get("reference"));
                  LOGGER.i("Get response from server " + response);
                  if (response.get(1)=="200"){
                    cached_product.put("ms_code", serial_product.get("ms_code"));
                    cached_product.put("reference", serial_product.get("reference"));
                    cached_product.put("description", serial_product.get("description"));
                    cached_product.put("name", response.get(0));
                  }else if (response.get(1)=="404"){
                    cached_product.put("ms_code", serial_product.get("ms_code"));
                    cached_product.put("reference", serial_product.get("reference"));
                    cached_product.put("description", serial_product.get("description"));
                    cached_product.put("name", "unknown product");
                  }else{
                    cached_product.put("ms_code", null);
                    cached_product.put("reference", null);
                    cached_product.put("description", null);
                    cached_product.put("name", response.get(0));
                  }
                }

                String ocr_label;
                Float rating;
                if (cached_product.get("ms_code")!=null && cached_product.get("name")!=null){
                  ocr_label = cached_product.get("description")+" \n: "+cached_product.get("name");
                  rating = 1f;
                }else if (cached_product.get("name")!=null){
                  ocr_label = "error : "+cached_product.get("name");
                  rating = 0f;
                }else{
                  ocr_label = "detecting...";
                  rating = 0f;
                }

                Classifier.Recognition ocr_result = new Classifier.Recognition("66", ocr_label, (float) rating, ocr_box);
                ocr_result.setLocation(ocr_box);
                mappedRecognitions.add(ocr_result);

                // Draw Logo box
                canvas.drawRect(location, paint);
                cropToFrameTransform.mapRect(location);
                result.setLocation(location);
                mappedRecognitions.add(result);
              }
            }

            // Invalidate product serial if no detection in 5 seconds
            idle_time = SystemClock.uptimeMillis() - detect_time;
            if (idle_time > 2000){
              serial_product.clear();
              cached_product.clear();
            }

            tracker.trackResults(mappedRecognitions, currTimestamp);
            trackingOverlay.postInvalidate();

            computingDetection = false;

            runOnUiThread(
                new Runnable() {
                  @Override
                  public void run() {
                    showFrameInfo(previewWidth + "x" + previewHeight);
                    showCropInfo(cropCopyBitmap.getWidth() + "x" + cropCopyBitmap.getHeight());
                    showInference(lastProcessingTimeMs + "ms");

                    if (switch_trigger.isChecked()){
                      gimmick_server.setEnabled(true);
                      trigger_button.setEnabled(true);
                    }else{
                      gimmick_server.setEnabled(false);
                      trigger_button.setEnabled(false);
                    }
                  }
                });
          }
        });
  }

  @Override
  protected int getLayoutId() {
    return R.layout.tfe_od_camera_connection_fragment_tracking;
  }

  @Override
  protected Size getDesiredPreviewFrameSize() {
    return DESIRED_PREVIEW_SIZE;
  }

  // Which detection model to use: by default uses Tensorflow Object Detection API frozen
  // checkpoints.
  private enum DetectorMode {
    TF_OD_API;
  }

  @Override
  protected void setUseNNAPI(final boolean isChecked) {
    runInBackground(() -> detector.setUseNNAPI(isChecked));
  }

  @Override
  protected void setNumThreads(final int numThreads) {
    runInBackground(() -> detector.setNumThreads(numThreads));
  }


}
