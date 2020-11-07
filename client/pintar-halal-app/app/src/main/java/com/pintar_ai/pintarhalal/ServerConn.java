package com.pintar_ai.pintarhalal;


import android.os.AsyncTask;
import android.util.Base64;
import android.util.JsonReader;
import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.lang.ref.WeakReference;
import java.net.HttpURLConnection;
import java.net.Socket;
import java.net.URL;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Timer;
import java.util.TimerTask;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;


public class ServerConn{

    public Socket toServer;
    public DataOutputStream outStream=null;
    private BlockingQueue<Map<String,String>> queue = new LinkedBlockingQueue<>(80);
    private String ip;
    private String server;
    private long ticks = 0;
    private Timer timer;

    ServerConn(String serverIP) {
        this.server=  "http://"+serverIP;
    }

    public void InsertOnboardParameter(Map data) {
        queue.add(data);
    }


    private void setPostRequestContent(HttpURLConnection conn,
                                       JSONObject jsonObject) throws IOException {

        OutputStream os = conn.getOutputStream();
        BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(os, "UTF-8"));
        writer.write(jsonObject.toString());
        Log.i("HTTP request send json ", jsonObject.toString());
        writer.flush();
        writer.close();
        os.close();
    }

    public List<String> RequestGimmick(String gimmick_server){
        try {
            String urlString = "http://"+gimmick_server+"/gimick"; // URL to call
            Log.i("RequestGimmick send to ", urlString);
            JSONObject jsonParam = new JSONObject();
            jsonParam.put("request", true);
            JSONObject response = SendPost(urlString,jsonParam);
            if (response.has("error")){
                return Arrays.asList(response.getString("error"), "404");
            }else if (response.has("status")){
                return Arrays.asList(response.getString("status"), "200");
            }else{
                return Arrays.asList("cannot connect to server", "666");
            }
        } catch (Exception e) {
            System.out.println(e.getMessage());
            return Arrays.asList("Exception happened", "666");
        }
    }

    public List<String> RequestItem(String ms_code, String reference, Double longitude, Double latitude){
        try {
            String urlString = server+"/requestItem"; // URL to call
            JSONObject jsonParam = new JSONObject();
            jsonParam.put("mscode", ms_code);
            jsonParam.put("itemid", reference);
            jsonParam.put("longitude", longitude);
            jsonParam.put("latitude", latitude);
            JSONObject response = SendPost(urlString,jsonParam);
            if (response.has("error")){
                return Arrays.asList(response.getString("error"), "404");
            }else if (response.has("Item Name")){
                return Arrays.asList(response.getString("Item Name"), "200");
            }else{
                return Arrays.asList("cannot connect to server", "666");
            }
        } catch (Exception e) {
            System.out.println(e.getMessage());
            return Arrays.asList("Exception happened", "666");
        }
    }

    private JSONObject SendPost(String urlString, JSONObject jsonParam){
        try {
            URL url = new URL(urlString);

            // 1. create HttpURLConnection
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setConnectTimeout(1000); //set timeout to 1 seconds

            // 3. add JSON content to POST request body
            setPostRequestContent(conn, jsonParam);

            // 4. make POST request to the given URL
            conn.connect();

            // 5. return response message
            String response = conn.getResponseMessage();
            Log.d("HTTP Response code: ", "> " + conn.getResponseCode());
            JSONObject response_json;
            if (conn.getResponseCode()==200){
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuffer buffer = new StringBuffer();
                String line = "";
                while ((line = reader.readLine()) != null) {
                    buffer.append(line+"\n");
                    Log.d("HTTP Response: ", "> " + line);   //here u ll get whole response...... :-)

                }
                response_json = new JSONObject(buffer.toString());
            }else{
                response_json = new JSONObject("{\"error\":\""+conn.getResponseMessage()+"\"}");
            }
            conn.disconnect();
            return response_json;
        } catch (Exception e) {
            Log.d("HTTP Response: ", "something is wrong");
            System.out.println(e.getMessage());
            JSONObject response_json = null;
            try {
                response_json = new JSONObject("{\"error\":\"Exception happened\"}");
            } catch (JSONException ex) {
                ex.printStackTrace();
            }
            return response_json;
        }
    }

}


